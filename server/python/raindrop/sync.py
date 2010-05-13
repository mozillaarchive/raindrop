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
import threading
import sys

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
  conductor.initialize()
  return conductor

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

  def __call__(self, src_id, src_rev):
    # XXX - we need a queue here!
    logger.debug("saw new document %r (%s) - kicking outgoing process",
                 src_id, src_rev)
    self.conductor._process_outgoing_row(src_id, src_rev)
    logger.debug("outgoing processing of %r (%s) finished",
                 src_id, src_rev)
    return [], False


class StopRequestedException(Exception):
  pass

class _SyncState:
  def __init__(self, acct):
    self.acct = acct
    self.control_event = threading.Event()
    self.is_syncing = False
    self.thread = None

# XXX - rename this to plain 'Conductor' and move to a different file.
# This 'conducts' synchronization, the work queues and the interactions with
# the extensions and database.
class SyncConductor(object):
  def __init__(self, pipeline):
    self.pipeline = pipeline
    self.doc_model = get_doc_model()
    self.stop_requested = False # are we waiting for things to finish?
    self.stop_forced = False # are we trying to force things to stop *now*?
    # Map of _SyncState objects, keyed by acct_id.  Once an item is added
    # it is never removed (ie, an account not appearing means it has never
    # been synced in this session)
    self._sync_states = {}

    self.outgoing_handlers = {}
    self.all_accounts = None
    self.num_new_items = None

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
      acct_id = acct.details['id']
      try:
        sync_state = self._sync_states[acct_id]
        state = 'synchronizing'
      except KeyError:
        state = 'idle'
      # XXXX - state = 'listening'

      acct_infos[acct_id] = {
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
    ret = []
    for acct in self.all_accounts:
      proto = acct.details['proto']
      if not options.protocols or proto in options.protocols:
        ret.append(acct)
      else:
          logger.info("Skipping account %r - protocol '%s' is disabled",
                      acct.details['id'], proto)
    return ret

  def _process_outgoing_row(self, src_id, src_rev):
    out_doc = self.doc_model.open_documents_by_id([src_id])[0]
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
        logger.debug("document %r has source %r", look_doc['_id'], ext_data['rd_source'])
        if ext_data['rd_source'] is None:
          src_doc = look_doc
          logger.debug("source for %r is %r (created by %r)", out_doc['_id'],
                      src_doc['_id'], ext_id)
          break
        these.append(ext_data['rd_source'][0])
      if src_doc is not None:
        break
      # add the ones we found to the look list.
      new = self.doc_model.open_documents_by_id(these)
      if logger.isEnabledFor(logging.DEBUG):
        for id, new_doc in zip(these, new):
          if new_doc is None:
            logger.debug('potential source doc %r does not exist', id)
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
      d = sender.startSend(self, src_doc, out_doc)
      if d:
        break

  def sync(self, options, incoming=True, outgoing=False, wait=False):
    assert not outgoing, "this isn't implemented"
    if incoming:
      self.sync_incoming(options)
    if wait:
      self.wait_for_sync()

  def provide_schema_items(self, items):
    self.pipeline.provide_schema_items(items)
    self.num_new_items += len(items)

  def _record_sync_status(self):
    rd_key = ["raindrop", "sync-status"]
    schema_id = 'rd.core.sync-status'
    # see if an existing schema exists to get the existing number.
    si = self.doc_model.open_schemas([(rd_key, schema_id)])[0]
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
    self.pipeline.provide_schema_items([si])
    self.num_new_items = None

  def sync_incoming(self, options):
    assert self.num_new_items is None # eek - we didn't reset correctly...
    self.num_new_items = 0
    # start synching all 'incoming' accounts.
    accts = self._get_specified_accounts(options)
    if not accts:
      logger.warn("No accounts are configured - nothing to sync")
      return

    for account in accts:
      acct_id = account.details['id']
      try:
        state = self._sync_states[acct_id]
      except KeyError:
        state = _SyncState(account)
        state.is_syncing = True
        state.thread = threading.Thread(target=self._sync_one_loop,
                                        args=(state, options))
        self._sync_states[acct_id] = state
        state.thread.start()
      else:
        # already a state for this account - set the control event to
        # wake it up
        state.control_event.set()

  def stop_sync(self, forced=True):
    self.stop_requested = True
    self.stop_forced = forced
    for s in self._sync_states.itervalues():
      s.control_event.set()

    for acct_id, s in self._sync_states.iteritems():
      t = s.thread
      if t is None:
        # thread completed
        continue
      logger.debug("waiting for '%s' to complete", acct_id)
      timeout = 10 if forced else None
      t.join(timeout)
      if t.isAlive():
        logger.error("Failed to stop sync of account '%s' - timed out",
                     acct_id)
    self._sync_states.clear()
    self._record_sync_status()
    logger.debug("syncing has stopped")

  def wait_for_sync(self):
    # wait for existing ones to complete, then return...
    self.stop_sync(False)

  def _sync_one_loop(self, sync_state, options):
    acct_id = sync_state.acct.details['id']
    try:
      self._do_sync_one_loop(sync_state, options)
    except:
      logger.exception("sync of account '%s' failed", acct_id)
    self._sync_states[acct_id].thread = None

  def _do_sync_one_loop(self, sync_state, options):
    account = sync_state.acct
    acct_name = account.details.get('name', '(un-named)')
    # Note we always perform one iteration before checking self.stop_requested
    # as our caller may start our thread, then immediately perform a
    # non-forced stop request to wait for us to complete.
    while True:
      # start synching
      logger.info('Starting sync of %s account: %s',
                  account.details['proto'], acct_name)
      sync_state.is_syncing = True
      try:
        account.startSync(self, options)
        logger.debug("Account %r finished successfully", acct_name)
      except (KeyboardInterrupt, StopRequestedException):
        logger.debug('sync of account %s was interrupted', acct_name)
        break
      except Exception:
        logger.exception('sync of account %s failed', acct_name)
        # but we retry if requested...
        # XXX - report status???
        if options.stop_on_error:
          logger.info("--stop-on-error specified - requesting stop")
          self.stop_sync()
          break
      finally:
        sync_state.is_syncing = False

      if self.stop_requested:
        break
      if options.repeat_after:
        timeout = time.time() + options.repeat_after
      else:
        timeout = None
      sync_state.control_event.wait(timeout=timeout)
      sync_state.control_event.clear()
      if self.stop_requested:
        break

  def apply_with_retry(self, acct, on_failed, func, *args, **kw):
    acct_det = acct.details
    acct_id = acct_det['id']
    try:
      control_event = self._sync_states[acct_id].control_event
    except KeyError:
      # must be outgoing
      control_event = None
    num_retries = acct_det.get('retry_count', acct.def_retry_count)
    backoff = acct_det.get('retry_backoff', acct.def_retry_backoff)
    backoff_max = acct_det.get('retry_backoff_max', acct.def_retry_backoff_max)
    while 1:
      try:
        return func(*args, **kw)
      except Exception, exc:
        num_retries -= 1
        if num_retries < 0:
          logger.info('ran out of retry attempts calling %s', func)
          raise
        # note on_failed may re-raise the exception if it isn't suitable for
        # retry
        on_failed(exc)
        if control_event is not None:
          control_event.wait(backoff)
        else:
          time.sleep(backoff)
        backoff = min(backoff*2, backoff_max)
        if control_event is not None and control_event.isSet():
          assert self.stop_requested
          if self.stop_forced:
            raise StopRequestedException()
          else:
            # This means 'retry now'.
            control_event.clear()
