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

""" This is the raindrop pipeline; it moves messages from their most raw
form to their most useful form.
"""
import time

from twisted.internet import defer, threads, task
from twisted.python.failure import Failure
from twisted.internet import reactor

from raindrop.model import DocumentSaveError

import extenv

import logging

logger = logging.getLogger(__name__)


class Extension(object):
    SMART = "smart" # a "smart" extension - handles dependencies etc itself.
    # a 'provider' of schema items; a schema is "complete" once a single
    # provider has run.
    PROVIDER = "provider"
    # An 'extender' - extends a schema written by a different extension.  If
    # only 'extenders' have provided schema fields, the schema is not yet
    # "complete", so extensions which depend on it aren't run and the field
    # values don't appear in the megaview.
    EXTENDER = "extender"

    ALL_CATEGORIES = (SMART, PROVIDER, EXTENDER)

    def __init__(self, id, doc, globs):
        self.id = id
        self.doc = doc
        # make the source schemas more convenient to use...
        # XXX - source_schema is deprecated
        if 'source_schemas' in doc:
            self.source_schemas = doc['source_schemas']
        else:
            self.source_schemas = [doc['source_schema']]
        self.confidence = doc.get('confidence')
        self.globs = globs
        self.running = False # for reentrancy testing...
        # the category - for now we have a default, but later should not!
        self.category = doc.get('category', self.PROVIDER)
        self.uses_dependencies = doc.get('uses_dependencies', False)
        if self.category not in self.ALL_CATEGORIES:
            logger.error("extension %r has invalid category %r (must be one of %s)",
                         id, self.category, self.ALL_CATEGORIES)

        self.handler = globs.get('handler')
        self.later_handler = globs.get('later_handler')

@defer.inlineCallbacks
def load_extensions(doc_model):
    extensions = {}
    # now try the DB - load everything with a rd.ext.workqueue schema
    key = ["schema_id", "rd.ext.workqueue"]
    ret = yield doc_model.open_view(key=key, reduce=False, include_docs=True)
    assert ret['rows'], "no extensions!"
    for row in ret['rows']:
        doc = row['doc']
        ext_id = doc['rd_key'][1]
        # some platforms get upset about \r\n, none get upset with \n.
        src = doc['code'].replace("\r\n", "\n")
        ct = doc.get('content_type')
        if ct != "application/x-python":
            logger.error("Content-type of %r is not supported", ct)
            continue
        try:
            co = compile(src, "<%s>" % ext_id, "exec")
        except SyntaxError, exc:
            logger.error("Failed to compile %r: %s", ext_id, exc)
            continue
        globs = {}
        try:
            exec co in globs
        except Exception, exc:
            logger.error("Failed to initialize extension %r: %s", ext_id, exc)
            continue
        assert ext_id not in extensions, ext_id # another with this ID??
        ext = Extension(ext_id, doc, globs)
        if ext.handler is None or not callable(ext.handler):
            logger.error("source-code in extension %r doesn't have a 'handler' function",
                         ext_id)
            continue
        extensions[ext_id] = ext
    defer.returnValue(extensions)


class Pipeline(object):
    """A manager for running items through the pipeline using various
    different strategies.
    """
    def __init__(self, doc_model, options):
        self.doc_model = doc_model
        self.options = options
        self.runner = None
        self._additional_processors = {}

    def initialize(self):
        ret = defer.Deferred()
        ret.callback(None)
        return ret

    def finalize(self):
        ret = defer.Deferred()
        ret.callback(None)
        return ret

    def add_processor(self, proc):
        proc_id = proc.ext.id
        assert proc_id not in self._additional_processors
        if proc_id in self._additional_processors:
            logger.warn("overwriting existing processor with duplicate ID %r",
                        proc_id)
        self._additional_processors[proc_id] = proc

    @defer.inlineCallbacks
    def provide_schema_items(self, items):
        """The main entry-point for 'providers' - mainly so we can do
        something smart as the provider finds new items - although what
        that 'smart' thing is hasn't yet been determined :)
        """
        _ = yield self.doc_model.create_schema_items(items)

    @defer.inlineCallbacks
    def get_extensions(self):
        ret = set()
        confidences = {}
        extensions = yield load_extensions(self.doc_model)
        for ext_id, ext in extensions.items():
            # record the confidence of all extensions, even if not all are
            # being used, so the 'aggregation' still works as expected.
            if ext.confidence is not None:
                confidences[ext.id] = ext.confidence
            ret.add(ext)
        self.doc_model.set_extension_confidences(confidences)
        defer.returnValue(ret)

    @defer.inlineCallbacks
    def get_queue_runners(self, spec_exts=None):
        """Get all the work-queue runners we know about"""
        if spec_exts is None:
            spec_exts = self.options.exts
        ret = []
        ret_names = set()
        for ext in (yield self.get_extensions()):
            qid = ext.id
            if spec_exts is None or qid in spec_exts:
                proc = ExtensionProcessor(self.doc_model, ext, self.options)
                schema_ids = ext.source_schemas
                qr = ProcessingQueueRunner(self.doc_model, proc, schema_ids, qid)
                ret.append(qr)
                ret_names.add(qid)
        # and the non-extension based ones.
        for ext_id, proc in self._additional_processors.iteritems():
            if spec_exts is None or ext_id in spec_exts:
                schema_ids = proc.ext.source_schemas
                qr = ProcessingQueueRunner(self.doc_model, proc, schema_ids, ext_id)
                ret.append(qr)
                ret_names.add(ext_id)

        defer.returnValue(ret)

    @defer.inlineCallbacks
    def start_processing(self, continuous, cont_stable_callback):
        assert self.runner is None, "already doing a process"
        pqrs = yield self.get_queue_runners()

        self.runner = StatefulQueueManager(self.doc_model, pqrs,
                                           self.options)
        try:
            _ = yield self.runner.run()
            if continuous:
                _ = yield self.runner.run_continuous(cont_stable_callback)
                
        finally:
            self.runner = None
        # count the number of errors - mainly for the test suite.
        nerr = sum([pqr.processor.num_errors for pqr in pqrs])
        # if an incoming processor is running, we also need to wait for that,
        # as it is what is doing the items created by the queue
        defer.returnValue(nerr)

    @defer.inlineCallbacks
    def unprocess(self):
        # Just nuke all items that have a 'rd_source' specified...
        # XXX - should do this in a loop with a limit to avoid chewing
        # all mem...
        if self.options.exts:
            runners = yield self.get_queue_runners()
            keys = [['ext_id', e.id] for e in exts]
            result = yield self.doc_model.open_view(
                                keys=keys, reduce=False)
            to_up = [{'_id': row['id'],
                      '_rev': row['value']['_rev'],
                      'rd_key': row['value']['rd_key'],
                      'rd_schema_id': row['value']['rd_schema_id'],
                      'rd_ext_id': row['key'][-1],
                      '_deleted': True
                      } for row in result['rows']]
        else:
            result = yield self.doc_model.open_view(
                                # skip NULL rows.
                                startkey=['source', ""],
                                endkey=['source', {}],
                                reduce=False)

            to_up = [{'_id': row['id'],
                      '_rev': row['value']['_rev'],
                      'rd_key': row['value']['rd_key'],
                      'rd_schema_id': row['value']['rd_schema_id'],
                      'rd_ext_id': row['value']['rd_ext_id'],
                      '_deleted': True
                      } for row in result['rows']]
        logger.info('deleting %d schemas', len(to_up))
        _ = yield self.doc_model.create_schema_items(to_up)

        # and rebuild our views
        logger.info("rebuilding all views...")
        _ = yield self.doc_model._update_important_views()

    @defer.inlineCallbacks
    def _reprocess_items(self, item_gen_factory, *factory_args):
        self.options.force = True # evil!
        runners = yield self.get_queue_runners()
        result = yield defer.DeferredList(
                    [r.process_queue(item_gen_factory(*factory_args))
                     for r in runners])
        num = sum([num for ok, num in result if ok])
        logger.info("reprocess made %d new docs", num)

    @defer.inlineCallbacks
    def reprocess(self):
        # We can't just reset all work-queues as there will be a race
        # (ie, one queue will be deleting a doc while it is being
        # processed by another.)
        # So by default this is like 'unprocess' - all docs without a rd_source are
        # reprocessed as if they were touched.  This should trigger the
        # first wave of extensions to re-run, which will trigger the next
        # etc.
        # However, if extensions are named, only those are reprocessed
        dm = self.doc_model
        def gen_em(this_result):
            to_proc = ((row['id'], row['value']['_rev'])
                       for row in this_result['rows'])
            for id, rev in to_proc:
                yield id, rev, None, None

        if not self.options.exts and not self.options.keys:
            # fetch all items with a null 'rd_source'
            result = yield dm.open_view(
                            key=['source', None],
                            reduce=False)
            logger.info("reprocess found %d source documents",
                        len(result['rows']))
            _ = yield self._reprocess_items(gen_em, result)
        elif not self.options.exts and self.options.keys:
            # no extensions, but a key - find the 'source' for this key
            # then walk it though all extensions...
            def gen_sources(rows):
                for row in rows:
                    val = row['value']
                    yield row['id'], val['_rev'], None, None

            keys = [['key-source', [k, None]]
                    for k in self.options.keys]
            result = yield dm.open_view(keys=keys, reduce=False)
                
            ps = yield self.get_ext_processors()
            for p in qs:
                p.options.force = True
            chugger = ProcessingQueueRunner(self.doc_model, ps)
            num = yield chugger.process_queue(gen_sources(result['rows']))
            logger.info("reprocess made %d new docs", num)
        else:
            # do each specified extension one at a time to avoid the races
            # if extensions depend on each other...
            for qr in (yield self.get_queue_runners()):
                # fetch all items this extension says it depends on
                if self.options.keys:
                    # But only for the specified rd_keys
                    keys = []
                    for k in self.options.keys:
                        for sch_id in qr.schema_ids:
                            keys.append(['key-schema_id', [k, sch_id]])
                else:
                    # all rd_keys...
                    keys=[['schema_id', sch_id] for sch_id in ext.source_schemas]
                result = yield dm.open_view(keys=keys,
                                            reduce=False)
                logger.info("reprocessing %s - %d docs", qr.queue_id,
                            len(result['rows']))
                _ = yield self._reprocess_items(gen_em, result)


    @defer.inlineCallbacks
    def start_retry_errors(self):
        """Attempt to re-process all messages for which our previous
        attempt generated an error.
        """
        # This is easy - just look for rd.core.error records and re-process
        # them - the rd.core.error record will be auto-deleted as we
        # re-process
        # It does have the bad side-effect of re-running all extensions which
        # also ran against the source of the error - that can be fixed, but
        # later...
        key = ["schema_id", "rd.core.error"]
        result = yield self.doc_model.open_view(key=key, reduce=False,
                                                include_docs=True)
        logger.info("found %d error records", len(result['rows']))
        def gen_em():
            for row in result['rows']:
                for ext_info in row['doc']['rd_schema_items'].itervalues():
                    src_id, src_rev = ext_info['rd_source']
                    yield src_id, src_rev, None, None

        _ = yield self._reprocess_items(gen_em)


class DocsBySeqIteratorFactory(object):
    """Reponsible for creating iterators based on a _changes view"""
    def __init__(self):
        self.stopping = False
        self.rows = None
        self.last_seq = None

    @defer.inlineCallbacks
    def _get_rows_wait(self, doc_model, start_seq):
        changes = []
        db = doc_model.db
        while not self.stopping and not changes:
            try:
                # The extra logging here is to help see a bug whereby couch
                # gets "stuck" and doesn't deliver changes that happen
                # concurrently - ie, a call here will block reading from
                # change xyz, even though the DB is at xyz+1
                logger.debug("%s opening _changes from seq %s", self, start_seq)
                results = yield db.listChanges(since=start_seq, feed='longpoll')
                changes = results.get('results', [])
                logger.debug("%s _changes from seq %s got %s results",
                             self, start_seq, len(changes))
            except ValueError:
                # A value error happens when we try and terminate the feed
                # and the json module fails to parse an empty string.
                # for now just assume it means we are being shut-down.
                logger.debug("closing _changes due to premature eof")
                break
        logger.debug("found %d continuous changes", len(changes))
        ret = [db._changes_row_to_old(c) for c in changes]
        defer.returnValue(ret)

    @defer.inlineCallbacks
    def initialize(self, doc_model, start_seq, limit=2000, stop_seq=None,
                   include_deps=False):
        if stop_seq is not None and start_seq >= stop_seq:
            defer.returnValue(False)

        assert stop_seq is None or stop_seq > start_seq
        self.stop_seq = stop_seq
        self.stopping = False
        if limit is None:
            rows = yield self._get_rows_wait(doc_model, start_seq)
        else:
            result = yield doc_model.db.listDocsBySeq(limit=limit,
                                                      startkey=start_seq)
            rows = result['rows']
        # We can only return False when there are no rows at all (ie, before
        # removing deleted items) else we will think we are at the very end.
        if not rows:
            self.last_seq = start_seq
            defer.returnValue(False) # nothing to do.

        # take the 'last_seq' before filtering deleted items
        self.last_seq = rows[-1]['key']
        self.rows = [r for r in rows
                     if 'error' not in r and 'deleted' not in r['value']]

        self.dep_rows = []
        if include_deps and self.rows:
            # find any documents which declare they depend on the documents
            # in the list, then lookup the "source" of that doc
            # (ie, the one that "normally" triggers that doc to re-run)
            # and return that source.
            all_ids = set()
            keys = []
            for row in self.rows:
                src_id = row['id']
                all_ids.add(src_id)
                try:
                    _, rd_key, schema_id = doc_model.split_doc_id(src_id)
                except ValueError:
                    # not a raindrop document - ignore it.
                    continue
                keys.append(["dep", [rd_key, schema_id]])

            results = yield doc_model.open_view(keys=keys, reduce=False)
            rows = results['rows']
            # Find all unique IDs.
            result_seq = set()
            for row in rows:
                src_id = row['value']['rd_source'][0]
                if src_id not in all_ids:
                    self.dep_rows.append(src_id)
                    all_ids.add(src_id)

        # Return True if this iterator has anything to do...
        defer.returnValue(True)

    def make_iter(self):
        """Make a new iterator over the rows"""
        def do_iter():
            mutter = lambda *args: None # might be useful one day for debugging...
            # Find the next row this queue can use.
            for row in self.rows:
                seq = row['key']
                if self.stop_seq is not None and seq >= self.stop_seq:
                    return
                if self.stopping:
                    return
                src_id = row['id']
                src_rev = row['value']['rev']
                yield src_id, src_rev, None, seq

            # and the 'dep' rows.
            # This is a little evil - we should arrange to 'interleave'
            # the deps and use the sequence of the 'parent'.
            for src_id in self.dep_rows:
                if self.stopping:
                    return
                yield src_id, None, None, None

        assert self.rows is not None, "not initialized"
        return do_iter()


# Used by the 'process' operation - runs all of the 'stateful work queues';
# when a single queue finishes, we restart any other queues already finished
# so they can then work on the documents since created by the running queues.
# Once all queues report they are at the end, we stop.
class QueueState:
    """helper object to remember the state of each queue"""
    def __init__(self):
        self.schema_item = None
        self.last_saved_seq = 0
        self.failure = None
        # XXX - can .running be replaced with 'queue_id in self.queue_iters'?
        self.running = False


class StatefulQueueManager(object):
    def __init__(self, dm, q_runners, options):
        assert q_runners, "nothing to do?"
        self.doc_model = dm
        self.stop_seq = None
        self.queues = q_runners
        self.queue_states = None # a list, parallel with self.queues.
        self.queue_iters = None # a dict keyed by qid for running queues.
        self.options = options
        self.status_msg_last = None

    def _start_q(self, q, q_state, def_done, do_incoming=False):
        assert not q_state.running, q
        q_state.running = True
        self._run_queue(q, q_state
                ).addBoth(self._q_done, q, q_state, def_done
                )

    @defer.inlineCallbacks
    def _start_q_continuous(self, q, q_state):
        assert not q_state.running, q
        q_state.running = True
        while q_state.running and not q_state.failure:
            try:
                _ = yield self._run_queue(q, q_state, None)
            except Exception:
                f = Failure()
                logger.error("queue %r failed:\n%s", q.queue_id, f.getTraceback())
                q_state.failure = f

        logger.debug("continuous processing of %r terminate: running=%s, failed=%s",
                     q.queue_id, q_state.running, bool(q_state.failure))
        q_state.running = False

    @defer.inlineCallbacks
    def _q_status(self):
        current_end = (yield self.doc_model.db.infoDB())['update_seq']
        lowest = (0xFFFFFFFFFFFF, None)
        nfailed = 0
        all_at_end = True
        for qlook, qstate in zip(self.queues, self.queue_states):
            if qstate.failure:
                nfailed += 1
                continue
            cs = qlook.current_seq or 0
            this = cs, qlook.queue_id
            if this < lowest:
                lowest = this
            if cs != current_end:
                all_at_end = False
        if all_at_end:
            msg = "all queues are up-to-date at sequence %s" % current_end
        else:
            behind = current_end - lowest[0]
            msg = "slowest queue is %r at %d (%d behind)" % \
                  (lowest[1], lowest[0], behind)
        if nfailed:
            msg += " - %d queues have failed" % nfailed
        if self.status_msg_last != msg:
            logger.info(msg)
            self.status_msg_last = msg

    @defer.inlineCallbacks
    def _q_check_stable(self, def_stop, stable_callback):
        # if all queues are at the end of _changes, then
        # fire the stable_callback.
        current_end = (yield self.doc_model.db.infoDB())['update_seq']
        logger.debug("checking is queue is stable - seq=%s", current_end)
        all_at_end = True
        for qlook, qstate in zip(self.queues, self.queue_states):
            if qstate.failure:
                continue
            cs = qlook.current_seq or 0
            # There seems to be a subtle timing problem with couchdb - if
            # I ask for changes since 'rev', in some cases things do not
            # return when rev+1 happens - as a result some queues can get
            # "stuck" at one *before* the end and are happily waiting for
            # a _changes notification that never comes (well - not before the
            # next external change causes us to see them.)
            # XXX - this is likely to cause a problem - if it can get 1 change
            # behind it can probably get more changes behind depending on the
            # level of concurrency...
            if cs != current_end and cs+1 != current_end:
                logger.debug("queue isn't yet stable - %r is at %s (end=%s)",
                             qlook.queue_id, cs, current_end)
                all_at_end = False
        if all_at_end:
            stop = yield defer.maybeDeferred(stable_callback, current_end)
            if stop:
                for q in self.queues:
                    q.running = False
                def_stop.callback(None)

    def _q_done(self, result, q, qstate, def_done):
        qstate.running = False
        failed = isinstance(result, Failure)
        if failed:
            logger.error("queue %r failed:\n%s", q.queue_id, result.getTraceback())
            qstate.failure = result
        else:
            logger.debug('queue %r reports it is complete at seq %s, done=%s',
                         q.queue_id, q.current_seq, result)
            assert result is True or result is False, repr(result)
        # First check for any other queues which are no longer running
        # but have a sequence less than ours.
        still_going = False
        nerrors = len([qs for qs in self.queue_states if qs.failure])
        stop_all = nerrors and self.options.stop_on_error
        for qlook, qslook in zip(self.queues, self.queue_states):
            if qslook.running:
                still_going = True
            # only restart queues if stop_on_error isn't specified.
            if stop_all:
                qilook = self.queue_iters.get(qlook.queue_id)
                if qilook is not None:
                    qilook.stopping = True
                continue

            if qlook is not q and not qslook.running and not qslook.failure and \
               qlook.current_seq < q.current_seq:
                still_going = True
                self._start_q(qlook, qslook, def_done, True)

        if not stop_all and not failed and not result:
            # The queue which called us back hasn't actually finished yet...
            still_going = True
            self._start_q(q, qstate, def_done, True)

        if not still_going:
            # All done.
            logger.info("All queues are finished!")
            def_done.callback(None)
        # else wait for one of the queues to finish and call us again...

    @defer.inlineCallbacks
    def _load_queue_state(self, qr):
        # first open our 'state' schema
        doc_model = self.doc_model
        rd_key = ['ext', qr.queue_id] # same rd used to save the extension source etc
        key = ['key-schema_id', [rd_key, 'rd.core.workqueue-state']]
        result = yield doc_model.open_view(key=key, reduce=False, include_docs=True)
        rows = result['rows']
        assert len(rows) in (0,1), result
        try:
            # ack - this is assuming each processor has a real 'extension' behind
            # it 
            src_id = qr.processor.ext.doc['_id']
            src_rev = qr.processor.ext.doc['_rev']
            # We set rd_source to the _id/_rev of the extension doc itself -
            # that way 'unprocess' etc all see these as 'derived'...
            rd_source = [src_id, src_rev]
        except AttributeError:
            rd_source = None
        state_info = {'rd_key' : rd_key,
                      'rd_source': rd_source,
                      # and similarly, say it was created by the extension itself.
                      'rd_ext_id': qr.queue_id,
                      'rd_schema_id': 'rd.core.workqueue-state',
                      }
        if len(rows) and 'doc' in rows[0]:
            doc = rows[0]['doc']
            state_info['_id'] = doc['_id']
            state_info['_rev'] = doc['_rev']
            state_info['items'] = {'seq' : doc.get('seq', 0)}
        else:
            state_info['items'] = {'seq': 0}
        ret = QueueState()
        ret.schema_item = state_info
        ret.last_saved_seq = state_info['items']['seq']
        defer.returnValue(ret)

    @defer.inlineCallbacks
    def _save_queue_state(self, state, current_seq, num_created):
        assert current_seq is not None
        si = state.schema_item
        seq = si['items']['seq'] = current_seq
        # We can chew 1000 'nothing to do' docs quickly next time...
        last_saved = state.last_saved_seq
        if num_created or (seq-last_saved) > 1000:
            logger.debug("flushing state doc at end of run...")
            docs = yield self.doc_model.create_schema_items([si])
            assert len(docs)==1, docs # only asked to save 1
            si['_rev'] = docs[0]['rev']
            state.last_saved_seq = seq
        else:
            logger.debug("no need to flush state doc")

    @defer.inlineCallbacks
    def _run_queue(self, q, qstate, num_to_process=2000):
        start_seq = qstate.schema_item['items']['seq']
        assert q.current_seq is None or q.current_seq == start_seq, (q.current_seq, start_seq)
        logger.debug("starting queue %r at sequence %s", q.queue_id, start_seq)
        # There is quite a performance penalty involved in getting the
        # dependencies for extensions which don't need them...
        include_deps = q.processor.ext.uses_dependencies

        iterfact = DocsBySeqIteratorFactory()
        assert self.stop_seq is None
        more = yield iterfact.initialize(self.doc_model, start_seq,
                                         num_to_process, self.stop_seq,
                                         include_deps=include_deps)
        logger.debug("queue %r has iterator with more=%s", q.queue_id, more)
        if not more:
            # queue is done (at the end)
            q.current_seq = iterfact.last_seq
            logger.debug('queue %r is at the end of _changes (stop_seq=%s)',
                         q.queue_id, q.current_seq)
            _ = yield self._save_queue_state(qstate, q.current_seq, 0)
            defer.returnValue(True)

        assert q.queue_id not in self.queue_iters
        src_gen = iterfact.make_iter()
        self.queue_iters[q.queue_id] = src_gen
        try:
            logger.debug("Work queue %r starting with sequence ID %d",
                         q.queue_id, start_seq)
            num_created = yield q.process_queue(src_gen)
        finally:
            del self.queue_iters[q.queue_id]

        # make sure we use the iterator factory's last_seq as the extensions
        # current_seq may not be correct if all items in the _changes feed
        # were deleted...
        q.current_seq = iterfact.last_seq
        _ = yield self._save_queue_state(qstate, q.current_seq, num_created)
        logger.debug("Work queue %r finished batch at sequence %s",
                     q.queue_id, q.current_seq)
        defer.returnValue(False)

    @defer.inlineCallbacks
    def run(self):
        dm = self.doc_model
        # load our queue states.
        assert self.queue_states is None
        self.queue_states = []
        for q in self.queues:
            self.queue_states.append((yield self._load_queue_state(q)))
        assert self.queue_iters is None
        self.queue_iters = {}

        # start a looping call to report the status while we run.
        lc = task.LoopingCall(self._q_status)
        lc.start(10, False)
        try:
            # and fire them off, waiting until all complete.
            def_done = defer.Deferred()
            for q, qs in zip(self.queues, self.queue_states):
                self._start_q(q, qs, def_done)
            _ = yield def_done
        finally:
            lc.stop()
        # update the views now...
        _ = yield self.doc_model._update_important_views()

    @defer.inlineCallbacks
    def run_continuous(self, stable_callback):
        done = defer.Deferred()
        # start a looping call to report the status while we run.
        lc1 = task.LoopingCall(self._q_status)
        lc1.start(10, False)
        lc2 = None
        if stable_callback is not None:
            # and a hacky task so a caller can be told when the queue becomes
            # "stable".
            lc2 = task.LoopingCall(self._q_check_stable, done, stable_callback)
            lc2.start(2, False)
        try:
            dm = self.doc_model
            # load our queue states.
            assert self.queue_states is not None
            logger.info("backlog complete - waiting for further changes")
            for q, qs in zip(self.queues, self.queue_states):
                self._start_q_continuous(q, qs)
            # and block until the 'stable_callback' says it is time to stop\
            # (which will be never if no callback was passed - in which case
            # Ctrl+C is the only way down)
            _ = yield done
        finally:
            lc1.stop()
            if lc2 is not None:
                lc2.stop()


class ProcessingQueueRunner(object):
    """A queue sequence runner - designed to run over an iterator
    of couch documents and run any of the extension objects which process the
    documents.
    """
    def __init__(self, doc_model, processor, schema_ids, queue_id):
        self.doc_model = doc_model
        self.processor = processor
        self.schema_ids = schema_ids
        self.queue_id = queue_id
        self.current_seq = None

    @defer.inlineCallbacks
    def process_queue(self, src_gen):
        """processes a number of items in a work-queue.
        """
        doc_model = self.doc_model
        num_created = 0
        schema_ids = self.schema_ids
        processor = self.processor
        queue_id = self.queue_id

        logger.debug("starting processing %r", queue_id)
        items = []
        pending = []
        # Given multiple extensions may write to the same document (as all
        # instances of the same schema are stored in the same document),
        # conflicts are inevitable.  When we see conflicts we simply retry a
        # few times in the expectation things will magically resolve
        # themselves.
        # This is more complicated than it need be due to our 'buffered
        # writing' - but performance really sucks without it...
        conflicts = []
        conflict_sources = {} # key is src_id, value is created doc id.
        # process until we run out.
        for src_id, src_rev, schema_id, seq in src_gen:
            if seq is not None: # 'dependency' rows have no seq...
                self.current_seq = seq
            if schema_id is None:
                try:
                    _, _, schema_id = doc_model.split_doc_id(src_id, decode_key=False)
                except ValueError, why:
                    logger.log(1, 'skipping document %r: %s', src_id, why)
                    continue

            if schema_id not in schema_ids:
                continue

            logger.debug("queue %r checking schema '%s' (doc %r/%s) at seq %s",
                         queue_id, schema_id, src_id, src_rev, self.current_seq)
            try:
                got, must_save = yield processor(src_id, src_rev)
            except extenv.ProcessLaterException, exc:
                # This extension has been asked to be called later at the
                # end of the batch - presumably to save doing duplicate work.
                logger.debug("queue %r asked for document %r/%s to be processed later (state=%r)",
                             queue_id, src_id, src_rev, exc.value)
                pending.append(exc.value)
                continue

            if not got:
                continue
            num_created += len(got)
            # note which src caused an item to be generated, incase we
            # conflict as we write them (see above - our 'buffering' makes
            # this necessary...)
            for si in got:
                doc_model.check_schema_item(si)
                did = doc_model.get_doc_id_for_schema_item(si)
                conflict_sources[did] = (src_id, src_rev)
            items.extend(got)
            if must_save or len(items)>20:
                try:
                    _ = yield doc_model.create_schema_items(items)
                except DocumentSaveError, exc:
                    conflicts.extend(exc.infos)
                items = []
        if items:
            try:
                _ = yield doc_model.create_schema_items(items)
            except DocumentSaveError, exc:
                conflicts.extend(exc.infos)

        # retry conflicts 3 times (yet another magic number)
        for i in range(3):
            if not conflicts:
                break
            logger.debug("handling %d conflicts", len(conflicts))
            new_conflicts = []
            for cinfo in conflicts:
                # find the src which created the conflicting item.
                src_id, src_rev = conflict_sources[cinfo['id']]
                logger.debug("redoing conflict when processing %r,%r", src_id,
                             src_rev)
                # and ask it to go again...
                got, _ = yield processor(src_id, src_rev)
                if got:
                    # don't bother batching when handling conflicts...
                    try:
                        _ = yield doc_model.create_schema_items(got)
                    except DocumentSaveError, exc:
                        new_conflicts.extend(exc.infos)
            logger.debug("handling the %d conflicts created %d new conflicts",
                         len(conflicts), len(new_conflicts))
            conflicts = new_conflicts
        else:
            # if we have remaining conflicts even after retrying, throw an error
            if conflicts:
                raise DocumentSaveError(conflicts)

        if pending:
            # If the extension asked for stuff to be done later, then now
            # is later!  We must do it per-batch, so the backlog processor
            # doesn't think we are done with this batch before we actually are.
            logger.debug("queue %r starting to process %d pending items",
                         queue_id, len(pending))
            got = yield self.processor.process_pending(pending)
            logger.debug("queue %r pending processing made %d items",
                         queue_id, len(got))
            if got:
                _ = yield doc_model.create_schema_items(got)
                num_created += len(got)

        logger.debug("finished processing %r to %r - %d processed",
                     queue_id, self.current_seq, num_created)
        defer.returnValue(num_created)


class ExtensionProcessor(object):
    """A class which manages the execution of a single extension over
    documents holding raindrop schemas"""
    def __init__(self, doc_model, ext, options):
        self.doc_model = doc_model
        self.ext = ext
        self.options = options
        self.num_errors = 0

    def _get_ext_env(self, context, src_doc):
        # Each ext has a single 'globals' which is updated before it is run;
        # therefore it is critical we don't accidently run the same extension
        # more than once concurrently
        if self.ext.running:
            raise RuntimeError, "%r is already running" % self.ext.id
        self.ext.running = True
        new_globs = extenv.get_ext_env(self.doc_model, context, src_doc,
                                       self.ext)
        self.ext.globs.update(new_globs)
        return self.ext.handler

    def _release_ext_env(self):
        assert self.ext.running
        self.ext.running = False

    def _merge_new_with_previous(self, new_items, docs_previous):
        # check the new items created against the 'source' documents created
        # previously by the extension.  Nuke the ones which were provided
        # before and which aren't now.  (This is most likely after an
        # 'rd.core.error' schema record is written, then the extension is
        # re-run and it successfully creates a 'real' schema)
        dm = self.doc_model
        ext_id = self.ext.id
        docs_this = set()
        for i in new_items:
            prev_key = dm.hashable_key((i['rd_key'], i['rd_schema_id']))
            docs_this.add(prev_key)
        for (prev_key, prev_val) in docs_previous.iteritems():
            if prev_key not in docs_this:
                si = {'rd_key': prev_val['rd_key'],
                      'rd_schema_id': prev_val['rd_schema_id'],
                      'rd_ext_id': ext_id,
                      '_deleted': True,
                      '_rev': prev_val['_rev'],
                      }
                new_items.insert(0, si)
                logger.debug('deleting previous schema item %(rd_schema_id)r'
                             ' by %(rd_ext_id)r for key %(rd_key)r', si)

    @defer.inlineCallbacks
    def process_pending(self, pending):
        new_items = []
        context = {'new_items': new_items}
        self._get_ext_env(context, None)
        func = self.ext.later_handler
        # Note we don't catch exceptions - failure stops this queue!
        try:
            _ = yield threads.deferToThread(func, pending)
        finally:
            self._release_ext_env()
        defer.returnValue(new_items)

    @defer.inlineCallbacks
    def __call__(self, src_id, src_rev):
        """The "real" entry-point to this processor"""
        dm = self.doc_model
        ext = self.ext
        ext_id = ext.id
        force = self.options.force

        # some extensions declare themselves as 'smart updaters' - they
        # are more efficiently able to deal with updating the records it
        # wrote last time than our brute-force approach.
        docs_previous = {}
        if ext.category == ext.SMART:
            # the extension says it can take care of everything related to
            # re-running.  Such extensions are unlikely to be able to be
            # correctly overridden, but that is life.
            pass
        elif ext.category in [ext.PROVIDER, ext.EXTENDER]:
            is_provider = ext.category!=ext.EXTENDER
            # We need to find *all* items previously written by this extension
            # so we can manage updating/removal of the old items.
            key = ['ext_id-source', [ext_id, src_id]]
            result = yield dm.open_view(key=key, reduce=False)
            rows = result['rows']
            if rows:
                if ext.uses_dependencies:
                    # we can't just check the source doc - assume the worst.
                    dirty = True
                else:
                    dirty = False
                    for row in rows:
                        assert 'error' not in row, row # views don't give error records!
                        prev_src = row['value']['rd_source']
                        # a hack to prevent us cycling to death - if our previous
                        # run of the extension created this document, just skip
                        # it.
                        # This might be an issue in the 'reprocess' case.
                        if prev_src is not None and prev_src[0] == src_id and \
                           row['value']['rd_schema_id'] in ext.source_schemas:
                            # This is illegal for a provider.
                            if is_provider:
                                raise ValueError("extension %r is configured to depend on schemas it previously wrote" %
                                                 ext_id)
                            # must be an extender, which is OK (see above)
                            logger.debug("skipping document %r - it depends on itself",
                                         src_id)
                            defer.returnValue((None, None))

                        if prev_src != [src_id, src_rev]:
                            dirty = True
                            break
                        # error rows are considered 'dirty'
                        cur_schema = row['value']['rd_schema_id']
                        if cur_schema == 'rd.core.error':
                            logger.debug('document %r generated previous error '
                                         'records - re-running', src_id)
                            dirty = True
                            break
            else:
                dirty = True
            if not dirty and not force:
                logger.debug("document %r is up-to-date", src_id)
                defer.returnValue((None, None))

            for row in rows:
                v = row['value']
                prev_key = dm.hashable_key((v['rd_key'], v['rd_schema_id']))
                logger.debug('noting previous schema item %(rd_schema_id)r by'
                             ' %(rd_ext_id)r for key %(rd_key)r', v)
                docs_previous[prev_key] = v
        else:
            raise RuntimeError("don't know what to do with category of extension %r: %r" %
                               (ext_id, ext.category))

        # Get the source-doc and process it.
        src_doc = (yield dm.open_documents_by_id([src_id]))[0]
        # Although we got this doc id directly from the _all_docs_by_seq view,
        # it is quite possible that the doc was deleted since we read that
        # view.  It could even have been updated - so if its not the exact
        # revision we need we just skip it - it will reappear later...
        if src_doc is None:
            logger.debug("skipping document %r - it's been deleted since we read the queue",
                         src_id)
            defer.returnValue((None, None))
        elif src_rev != None and src_doc['_rev'] != src_rev:
            logger.debug("skipping document %(_id)r - it's changed since we read the queue",
                         src_doc)
            defer.returnValue((None, None))

        # our caller should have filtered the list to only the schemas
        # our extensions cares about.
        assert src_doc['rd_schema_id'] in ext.source_schemas

        # If the source of this document is yet to see a schema written by
        # a 'schema provider', skip calling extensions which depend on this
        # doc - we just wait for a 'provider' to be called, at which time
        # the source doc will again trigger us being called again.
        if not src_doc.get('rd_schema_provider'):
            logger.debug("skipping document %(_id)r - it has yet to see a schema provider",
                         src_doc)
            defer.returnValue((None, None))

        # Now process it
        new_items = []
        context = {'new_items': new_items}
        logger.debug("calling %r with doc %r, rev %s", ext_id,
                     src_doc['_id'], src_doc['_rev'])

        # Our extensions are 'blocking', so use a thread...
        try:
            func = self._get_ext_env(context, src_doc)
            try:
                result = yield threads.deferToThread(func, src_doc)
            finally:
                self._release_ext_env()
        except extenv.ProcessLaterException, exc:
            assert not new_items, "extensions can't do now and later!"
            # we still need to delete the older ones created last time.
            self._merge_new_with_previous(new_items, docs_previous)
            if new_items:
                _ = yield self.doc_model.create_schema_items(new_items)
            # can't use simple 'raise' as the yield above prevents it.
            raise exc
        except:
            # handle_ext_failure may put error records into new_items.
            self._handle_ext_failure(Failure(), src_doc, new_items)
        else:
            if result is not None:
                # an extension returning a value implies they may be
                # confused?
                logger.warn("extension %r returned value %r which is ignored",
                            ext, result)

        logger.debug("extension %r generated %d new schemas", ext_id, len(new_items))

        self._merge_new_with_previous(new_items, docs_previous)
        # We try hard to batch writes; we earlier just checked to see if
        # only the same key was written, but that still failed.  Last
        # ditch attempt is to see if the extension made a query - if it
        # did, then it will probably query next time, and will probably
        # expect to see what it wrote last time
        must_save = 'did_query' in context
        if not must_save:
            # must also save now if they wrote a key for another item.
            for i in new_items:
                logger.debug('new schema item %(rd_schema_id)r by'
                             ' %(rd_ext_id)r for key %(rd_key)r', i)
                if i['rd_key'] != src_doc['rd_key']:
                    must_save = True
                    break
        defer.returnValue((new_items, must_save))

    def _handle_ext_failure(self, result, src_doc, new_items):
        # If a converter fails to
        # create a schema item, we can't just fail, or no later messages in the
        # DB will ever get processed!
        # So we write an 'error' schema and discard any it did manage to create
        assert isinstance(result, Failure)
        #if isinstance(result.value, twisted.web.error.Error):
        #    # eeek - a socket error connecting to couch; we want to abort
        #    # here rather than try to write an error record with the
        #    # connection failure details (but worse, that record might
        #    # actually be written - we might just be out of sockets...)
        #    result.raiseException()
        # XXX - later we should use the extension's log, but for now
        # use out log but include the extension name.
        logger.warn("Extension %r failed to process document %r: %s",
                    self.ext.id, src_doc['_id'], result.getTraceback())
        self.num_errors += 1
        if self.options.stop_on_error:
            logger.info("--stop-on-error specified - stopping queue")
            # Throw away any records emitted by *this* failure.
            new_items[:] = []
            result.raiseException()

        # and make the error record
        edoc = {'error_details': unicode(result)}
        if new_items:
            logger.info("discarding %d items created before the failure",
                        len(new_items))
        new_items[:] = [{'rd_key' : src_doc['rd_key'],
                         'rd_source': [src_doc['_id'], src_doc['_rev']],
                         'rd_schema_id': 'rd.core.error',
                         'rd_ext_id' : self.ext.id,
                         'items' : edoc,
                         }]
