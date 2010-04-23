# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Raindrop.
#
# The Initial Developer of the Original Code is
# Mozilla Messaging, Inc..
# Portions created by the Initial Developer are Copyright (C) 2009
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#

import logging
import time

from twisted.internet import reactor, defer
from twisted.python.failure import Failure
import twisted.web.error
import twisted.internet.error
import paisley

from . import proto as proto
from .config import get_config

logger = logging.getLogger(__name__)

from .model import get_doc_model

# XXX - we need a registry of 'outgoing source docs'.  As all of these
# are actually defined by extensions, we could have a flag on extensions to
# indicate if they are doing outgoing work, then we could determine this list.
source_schemas = ['rd.msg.outgoing.simple',
                  'rd.msg.seen',
                  'rd.msg.deleted',
# archived disabled until we know what to do with them.
#                  'rd.msg.archived',
                  ]


def get_conductor(pipeline):
  conductor = SyncConductor(pipeline)
  # We used to *need* a deferred here - but now initialize doesn't use
  # deferred we don't.  However, we stick with returning a deferred for the
  # sake of not yet adjusting the consumers of this (mainly in the tests)
  conductor.initialize()
  return defer.succeed(conductor)

class OutgoingExtension:
  def __init__(self, id, src_schemas):
    self.id = id
    self.source_schemas = src_schemas
    self.uses_dependencies = False

class OutgoingProcessor:
  def __init__(self, conductor, ext):
    self.conductor = conductor
    self.ext = ext
    self.num_errors = 0

  @defer.inlineCallbacks
  def __call__(self, src_id, src_rev):
    # XXX - we need a queue here!
    logger.debug("saw new document %r (%s) - kicking outgoing process",
                 src_id, src_rev)
    _ = yield self.conductor._process_outgoing_row(src_id, src_rev)
    logger.debug("outgoing processing of %r (%s) finished",
                 src_id, src_rev)
    defer.returnValue(([], False))

# XXX - rename this to plain 'Conductor' and move to a different file.
# This 'conducts' synchronization, the work queues and the interactions with
# the extensions and database.
class SyncConductor(object):
  def __init__(self, pipeline):
    self.pipeline = pipeline
    # apparently it is now considered 'good form' to pass reactors around, so
    # a future of multiple reactors is possible.
    # We capture it here, and all the things we 'conduct' use this reactor
    # (but later it should be passed to our ctor too)
    self.reactor = reactor
    self.doc_model = get_doc_model()

    self.accounts_syncing = []
    self.accounts_listening = set()
    self.outgoing_handlers = {}
    self.all_accounts = None
    self.calllaters_waiting = {} # keyed by ID, value is a IDelayedCall
    self.deferred = None
    self.num_new_items = None

  def _ohNoes(self, failure, *args, **kwargs):
    logger.error('OH NOES! failure! %s', failure)

  def initialize(self):
    self._load_accounts()
    # ask the pipeline to tell us when new outgoing schemas arrive.
    # Note we add a new extension per schema, so each sender can procede
    # (or fail) at its own pace.
    for sch_id in self.outgoing_handlers.iterkeys():
      ext_id = "outgoing-" + sch_id
      ext = OutgoingExtension(ext_id, [sch_id])
      proc = OutgoingProcessor(self, ext)
      self.pipeline.add_processor(proc)

  def get_status_ob(self):
    acct_infos = {}
    for acct in self.all_accounts:
      if acct in self.accounts_syncing:
        state = 'synchronizing'
      elif acct in self.accounts_listening:
        state = 'listening'
      else:
        state = 'idle'

      acct_infos[acct.details['id']] = {
                         'state': state,
                         'status': acct.status,
                         }
    return {'accounts' : acct_infos}

  def _load_accounts(self):
    # We used to store account info (other than the password) in couch docs.
    # This creates a hole whereby someone could replace the 'host' name in
    # couchdb with a server under their control, then harvest the password
    # as we attempt to login.
    # We now use only the file-system for account info (and our entry-points
    # for changing account info always updates the password when things are
    # changed)
    # XXX - this still needs work though, as the details are only read
    # once and not updated.  This should be OK in the short-term though, as
    # out sync process does it's job then terminates, so subsequent runs
    # will get new details.
    # get all accounts from the couch.
    assert self.all_accounts is None, "only call me once."
    self.all_accounts = []
    for acct_name, acct_info in get_config().accounts.iteritems():
      acct_id = acct_info['id']
      if not acct_info.get('enabled', True):
        logger.info("account %r is disabled", acct_id)
        continue
      try:
          account_proto = acct_info['proto']
          logger.debug("Found account using protocol %s", account_proto)
      except KeyError:
          logger.error("account %(id)r has no protocol specified - ignoring",
                       acct_info)
          continue
      if account_proto in proto.protocols:
        account = proto.protocols[account_proto](self.doc_model, acct_info)
        logger.debug('loaded %s account: %s', account_proto,
                     acct_info.get('name', acct_id))
        self.all_accounts.append(account)
        # Can it handle any 'outgoing' schemas?
        out_schemas = account.rd_outgoing_schemas
        for sid in (out_schemas or []):
          existing = self.outgoing_handlers.setdefault(sid, [])
          existing.append(account)
      else:
        logger.error("Don't know what to do with account protocol: %s",
                     account_proto)

  def _get_specified_accounts(self, options):
    assert self.all_accounts # no accounts loaded?
    ret = []
    for acct in self.all_accounts:
      proto = acct.details['proto']
      if not options.protocols or proto in options.protocols:
        ret.append(acct)
      else:
          logger.info("Skipping account %r - protocol '%s' is disabled",
                      acct.details['id'], proto)
    return ret

  @defer.inlineCallbacks
  def _process_outgoing_row(self, src_id, src_rev):
    out_doc = (yield self.doc_model.open_documents_by_id([src_id]))[0]
    if out_doc['_rev'] != src_rev:
      # this can happen if the 'src_doc' is the same doc as the 'outgoing'
      # doc - the outgoing process modified the document to record it was
      # sent.
      logger.debug('the outgoing document changed since it was processed.')
      return
    logger.info('processing outgoing message with schema %s',
                out_doc['rd_schema_id'])
    # locate the 'source' row - this involves walking backward through the
    # rd_source attribute until we find an emtpy one.  Fortunately the
    # chain should be fairly small, so shouldn't cost too much (an alternative
    # would be to issue one request for all docs with this rd_key and walk
    # the resulting list.
    look_docs = [out_doc]
    src_doc = None
    while look_docs:
      look_doc = look_docs.pop()
      if look_doc is None:
        continue
      these = []
      for ext_id, ext_data in look_doc['rd_schema_items'].iteritems():
        if ext_data['rd_source'] is None:
          src_doc = look_doc
          logger.info("source for %r is %r (created by %r)", out_doc['_id'],
                      src_doc['_id'], ext_id)
          break
        these.append(ext_data['rd_source'][0])
      if src_doc is not None:
        break
      # add the ones we found to the look list.
      new = yield self.doc_model.open_documents_by_id(these)
      look_docs.extend(new)
    if src_doc is None:
      logger.error("found outgoing row '%(_id)s' but failed to find a source",
                   out_doc)
      return

    out_state = src_doc.get('outgoing_state')
    if out_state != 'outgoing':
      logger.info('skipping outgoing doc %r - outgoing state is %r',
                  src_doc['_id'], out_state)
      return

    senders = self.outgoing_handlers[out_doc['rd_schema_id']]
    # There may be multiple senders, but first one to process it wins
    # (eg, outgoing imap items have one per account, but each account may be
    # passed one for a different account - it just ignores it, so we continue
    # the rest of the accounts until one says "yes, it is mine!")
    for sender in senders:
      d = yield sender.startSend(self, src_doc, out_doc)
      if d:
        break

  @defer.inlineCallbacks
  def _do_sync_outgoing(self):
    keys = []
    for ss in source_schemas:
      keys.append([ss, 'outgoing_state', 'outgoing'])

    dl = []
    result = yield self.doc_model.open_view(keys=keys, reduce=False)
    for row in result['rows']:
      logger.info("found outgoing document %(id)r", row)
      try:
        def_done = self._process_outgoing_row(row)
        dl.append(def_done)
      except Exception:
        logger.error("Failed to process doc %r\n%s", row['id'],
                     Failure().getTraceback())
    defer.returnValue(dl)

  def sync(self, options, incoming=True, outgoing=True):
    dl = []
    if outgoing:
      dl.append(self.sync_outgoing(options))
    if incoming:
      dl.append(self.sync_incoming(options))
    return defer.DeferredList(dl)

  @defer.inlineCallbacks
  def provide_schema_items(self, items):
    _ = yield self.pipeline.provide_schema_items(items)
    self.num_new_items += len(items)

  @defer.inlineCallbacks
  def sync_outgoing(self, options):
      return ###############
      # start looking for outgoing schemas to sync...
      dl = (yield self._do_sync_outgoing())
      _ = yield defer.DeferredList(dl)

  @defer.inlineCallbacks
  def _record_sync_status(self, result):
    rd_key = ["raindrop", "sync-status"]
    schema_id = 'rd.core.sync-status'
    # see if an existing schema exists to get the existing number.
    si = (yield self.doc_model.open_schemas([(rd_key, schema_id)]))[0]
    num_syncs = 0 if si is None else si['num_syncs']

    # a timestamp in UTC
    items = {'timestamp': time.mktime(time.gmtime()),
             'new_items': self.num_new_items,
             'num_syncs': num_syncs + 1,
             'status': self.get_status_ob(),
    }
    # The 'state' bit - this is the source of an outgoing message.
    if si is None:
      # first time around 
      items['outgoing_state'] = 'outgoing'
      items['sent_state'] = None
    else:
      items['sent_state'] = si.get('sent_state')
      items['outgoing_state'] = si.get('outgoing_state')
    si = {'rd_key': rd_key,
          'rd_schema_id': schema_id,
          'rd_source': None,
          'rd_ext_id': 'rd.core',
          'items': items,
    }
    _ = yield self.pipeline.provide_schema_items([si])
    self.num_new_items = None

  def sync_incoming(self, options):
    assert self.num_new_items is None # eek - we didn't reset correctly...
    self.num_new_items = 0
    if self.deferred is None:
      self.deferred = defer.Deferred()
      self.deferred.addCallback(self._record_sync_status)
    # start synching all 'incoming' accounts.
    accts = self._get_specified_accounts(options)
    for account in accts:
      if account in self.accounts_syncing:
        logger.info("skipping acct %(id)s - already synching...",
                    account.details)
        continue
      # cancel an old 'callLater' if one is scheduled.
      try:
        self.calllaters_waiting.pop(account.details['id']).cancel()
      except (KeyError, twisted.internet.error.AlreadyCalled):
        # either not in the map, or is in the map but we are being called
        # because of it firing.  Note the 'pop' works even if we are
        # already called.
        pass
      # start synching
      logger.info('Starting sync of %s account: %s',
                  account.details['proto'],
                  account.details.get('name', '(un-named)'))
      def_done = account.startSync(self, options)
      if def_done is not None:
        self.accounts_syncing.append(account)
        def_done.addBoth(self._cb_sync_finished, account, options)

    # return a deferred that fires once everything is completely done.
    ret = self.deferred
    self._check_if_finished()
    return ret

  def _cb_sync_finished(self, result, account, options):
    acct_id = account.details['id']
    if isinstance(result, Failure):
      logger.error("Account %s failed with an error: %s", account, result)
      if options.stop_on_error:
        logger.info("--stop-on-error specified - re-throwing error")
        result.raiseException()
    else:
      logger.debug("Account %r finished successfully", acct_id)
      if options.repeat_after:
        logger.info("account %r finished - rescheduling for %d seconds",
                    acct_id, options.repeat_after)
        cl = self.reactor.callLater(options.repeat_after, self.sync, options)
        self.calllaters_waiting[acct_id] = cl

    assert account in self.accounts_syncing, (account, self.accounts_syncing)
    self.accounts_syncing.remove(account)
    self._check_if_finished()

  def _check_if_finished(self):
    if not self.accounts_syncing and not self.calllaters_waiting:
      logger.info("all incoming accounts have finished synchronizing")
      d = self.deferred
      self.deferred = None
      d.callback(None)
