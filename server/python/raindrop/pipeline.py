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
import sys
import time
import itertools
import threading

from raindrop.model import DocumentSaveError
from raindrop.changesiter import ChangesIterFactory

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
        if self.source_schemas is None:
            self.filter = globs.get('filter')
            if not self.filter:
                logger.error("extension %r has null source_schemas but doesn't"
                             " provide a filter function")
        else:
            # a default filter which checks the schema id is one we want.
            self.filter = lambda src_id, src_rev, schema_id: schema_id in self.source_schemas

def load_extensions(doc_model):
    extensions = {}
    # now try the DB - load everything with a rd.ext.workqueue schema
    key = ["schema_id", "rd.ext.workqueue"]
    ret = doc_model.open_view(key=key, reduce=False, include_docs=True)
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
    return extensions


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
        pass

    def finalize(self):
        pass

    def add_processor(self, proc):
        proc_id = proc.ext.id
        assert proc_id not in self._additional_processors
        if proc_id in self._additional_processors:
            logger.warn("overwriting existing processor with duplicate ID %r",
                        proc_id)
        self._additional_processors[proc_id] = proc

    def provide_schema_items(self, items):
        """The main entry-point for 'providers' - mainly so we can do
        something smart as the provider finds new items - although what
        that 'smart' thing is hasn't yet been determined :)
        """
        self.doc_model.create_schema_items(items)

    def get_extensions(self):
        ret = set()
        confidences = {}
        extensions = load_extensions(self.doc_model)
        for ext_id, ext in extensions.items():
            # record the confidence of all extensions, even if not all are
            # being used, so the 'aggregation' still works as expected.
            if ext.confidence is not None:
                confidences[ext.id] = ext.confidence
            ret.add(ext)
        self.doc_model.set_extension_confidences(confidences)
        return ret

    def get_queue_runners(self, spec_exts=None):
        """Get all the work-queue runners we know about"""
        if spec_exts is None:
            spec_exts = self.options.exts
        ret = []
        for ext in self.get_extensions():
            qid = ext.id
            if spec_exts is None or qid in spec_exts:
                proc = ExtensionProcessor(self.doc_model, ext, self.options)
                qr = ProcessingQueueRunner(self.doc_model, proc, qid)
                ret.append(qr)
        # and the non-extension based ones.
        for ext_id, proc in self._additional_processors.iteritems():
            if spec_exts is None or ext_id in spec_exts:
                qr = ProcessingQueueRunner(self.doc_model, proc, ext_id)
                ret.append(qr)
        return ret

    def start_processing(self, cont_stable_callback):
        assert self.runner is None, "already doing a process"
        pqrs = self.get_queue_runners()

        self.runner = StatefulQueueManager(self.doc_model, pqrs,
                                           self.options)
        try:
            self.runner.run(cont_stable_callback)
        finally:
            self.runner = None
        # count the number of errors - mainly for the test suite.
        nerr = sum([pqr.processor.num_errors for pqr in pqrs])
        # if an incoming processor is running, we also need to wait for that,
        # as it is what is doing the items created by the queue
        return nerr

    def unprocess(self):
        # Just nuke all items that have a 'rd_source' specified...
        # XXX - should do this in a loop with a limit to avoid chewing
        # all mem...
        if self.options.exts:
            runners = self.get_queue_runners()
            keys = [['ext_id', r.queue_id] for r in runners]
            result = self.doc_model.open_view(keys=keys, reduce=False)
            to_up = [{'_id': row['id'],
                      '_rev': row['value']['_rev'],
                      'rd_key': row['value']['rd_key'],
                      'rd_schema_id': row['value']['rd_schema_id'],
                      'rd_ext_id': row['key'][-1],
                      '_deleted': True
                      } for row in result['rows']]
        else:
            result = self.doc_model.open_view(
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
        if to_up:
            self.doc_model.create_schema_items(to_up)

        # and rebuild our views
        logger.info("rebuilding all views...")
        self.doc_model._update_important_views()

    def _reprocess_items(self, item_gen_factory, *factory_args):
        self.options.force = True # evil!
        runners = self.get_queue_runners()
        results = [r.process_queue(item_gen_factory(*factory_args)) 
                   for r in runners]
        num = sum(results)
        logger.info("reprocess made %d new docs", num)

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
            result = dm.open_view(
                            key=['source', None],
                            reduce=False)
            logger.info("reprocess found %d source documents",
                        len(result['rows']))
            self._reprocess_items(gen_em, result)
        else:
            # do each specified extension one at a time to avoid the races
            # if extensions depend on each other...
            for qr in self.get_queue_runners():
                # fetch all items this extension says it depends on
                if self.options.keys:
                    # But only for the specified rd_keys
                    keys = []
                    for k in self.options.keys:
                        for sch_id in qr.schema_ids:
                            keys.append(['key-schema_id', [k, sch_id]])
                else:
                    # all rd_keys...
                    keys=[['schema_id', sch_id] for sch_id in qr.schema_ids]
                result = dm.open_view(keys=keys,
                                            reduce=False)
                logger.info("reprocessing %s - %d docs", qr.queue_id,
                            len(result['rows']))
                self._reprocess_items(gen_em, result)


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
        result = self.doc_model.open_view(key=key, reduce=False,
                                          include_docs=True)
        logger.info("found %d error records", len(result['rows']))
        def gen_em():
            for row in result['rows']:
                for ext_info in row['doc']['rd_schema_items'].itervalues():
                    src_id, src_rev = ext_info['rd_source']
                    yield src_id, src_rev, None, None

        self._reprocess_items(gen_em)


# Used by the 'process' operation - runs all of the 'stateful work queues';
# Each is run continuously and independenly of the others - but once all
# queues report they are blocked on waiting for new changes at the same
# sequence, we assume that means it is the last sequence, so we (optionally)
# stop (or just wait forever for future changes).
class QueueState:
    """helper object to remember the state of each queue"""
    def __init__(self):
        self.schema_item = None
        self.last_saved_seq = 0
        self.failure = None
        self.running = False


class StatefulQueueManager(object):
    def __init__(self, dm, q_runners, options):
        assert q_runners, "nothing to do?"
        self.doc_model = dm
        self.queues = q_runners
        self.queue_states = None # a list, parallel with self.queues.
        self.options = options
        self.status_msg_last = None

    def _q_status(self):
        current_end = self.doc_model.db.infoDB()['update_seq']
        lowest = (0xFFFFFFFFFFFF, None)
        nfailed = 0
        all_at_end = True
        for qlook, qstate in zip(self.queues, self.queue_states):
            if qstate.failure:
                nfailed += 1
                continue
            cs = qstate.feed.current_seq
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

    def _load_queue_state(self, qr):
        # first open our 'state' schema
        doc_model = self.doc_model
        rd_key = ['ext', qr.queue_id] # same rd used to save the extension source etc
        key = ['key-schema_id', [rd_key, 'rd.core.workqueue-state']]
        result = doc_model.open_view(key=key, reduce=False, include_docs=True)
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
        return ret

    def _save_queue_state(self, state, current_seq, num_created):
        assert current_seq is not None
        si = state.schema_item
        seq = si['items']['seq'] = current_seq
        # We can chew 1000 'nothing to do' docs quickly next time...
        last_saved = state.last_saved_seq
        if num_created or (seq-last_saved) > 1000:
            logger.debug("flushing state doc at end of run...")
            docs = self.doc_model.create_schema_items([si])
            assert len(docs)==1, docs # only asked to save 1
            si['_rev'] = docs[0]['rev']
            state.last_saved_seq = seq
        else:
            logger.debug("no need to flush state doc")

    def _run_queue(self, q, qstate, batch_size=2000):
        logger.debug("initializing queue %r at sequence %s", q.queue_id, qstate.feed.current_seq)
        qstate.running = True
        qstate.failure = None
        while qstate.running:
            batchiter = qstate.feed.make_iter(batch_size)
            logger.debug("starting batch for queue %r at sequence %s", q.queue_id, qstate.feed.current_seq)
            num_created = q.process_queue(batchiter)
            logger.debug("Work queue %r finished batch at sequence %s",
                         q.queue_id, qstate.feed.current_seq)
            self._save_queue_state(qstate, qstate.feed.current_seq, 0)

    def _worker_thread(self, q, qs):
        try:
            self._run_queue(q, qs)
        except Exception, exc:
            logger.exception('queue %r failed seriously!', q.queue_id)
            qs.failure = exc
        qs.running = False

    def _stop_all(self):
        for qs in self.queue_states:
            qs.feed.stop()
            qs.running = False

    def run(self, stable_callback):
        dm = self.doc_model
        # load our queue states.
        assert self.queue_states is None
        self.queue_states = []
        for q in self.queues:
            qs = self._load_queue_state(q)
            self.queue_states.append(qs)
            qs.feed = ChangesIterFactory()
            start_seq = qs.schema_item['items']['seq']
            # There is quite a performance penalty involved in getting the
            # dependencies for extensions which don't need them...
            include_deps = q.processor.ext.uses_dependencies
            qs.feed.initialize(self.doc_model, start_seq, include_deps=include_deps)

        last_status_tick = time.time()

        # we get a large perf increase by setting the check interval high;
        # as we are heavily IO bound this doesn't affect thread switching
        # as it happens on each couch request anyway...
        old_check_interval = sys.getcheckinterval()
        sys.setcheckinterval(5000)

        workers = []
        for q, qs in zip(self.queues, self.queue_states):
            t = threading.Thread(target=self._worker_thread,
                                 args=(q, qs))
            t.setDaemon(True) # incase one gets truly stuck...
            t.start()
            workers.append(t)

        finished = False
        try:
            while not finished:
                # wake up once per second to check status etc.
                time.sleep(1)
                if time.time()-10 > last_status_tick:
                    self._q_status()
                    last_status_tick = time.time()

                # See if each of the changes feeds are blocked at the same
                # sequence number.
                all_seqs = set()
                for q, qs in zip(self.queues, self.queue_states):
                    if qs.running:
                        if not qs.feed.is_waiting:
                            break
                        all_seqs.add(qs.feed.current_seq)
                else:
                    # didn't break, so all are blocked somewhere.  Check all
                    # at the same point.
                    all_at_end = len(all_seqs)==1
                    if all_at_end:
                        end_seq = all_seqs.pop()
                        logger.debug('all queues are paused at seq %s', end_seq)
                        if stable_callback is None:
                            finished = True
                        else:
                            finished = stable_callback(end_seq)
        finally:
            logger.debug('queue processing complete - stopping workers')
            # kill the worker threads.
            self._stop_all()
            for w in workers:
                w.join(10)
                if w.isAlive():
                    logger.warn("failed to wait for worker thread to complete")
            sys.setcheckinterval(old_check_interval)

        # update the views now...
        self.doc_model._update_important_views()


class ProcessingQueueRunner(object):
    """A queue sequence runner - designed to run over an iterator
    of couch documents and run any of the extension objects which process the
    documents.
    """
    def __init__(self, doc_model, processor, queue_id):
        self.doc_model = doc_model
        self.processor = processor
        self.queue_id = queue_id

    def process_queue(self, src_gen):
        """processes a number of items in a work-queue.
        """
        doc_model = self.doc_model
        num_created = 0
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
        last_seq = None
        for src_id, src_rev, schema_id, seq in src_gen:
            if seq is not None: # 'dependency' rows have no seq...
                last_seq = seq
            if schema_id is None:
                try:
                    _, _, schema_id = doc_model.split_doc_id(src_id, decode_key=False)
                except ValueError, why:
                    logger.log(1, 'skipping document %r: %s', src_id, why)
                    continue

            try:
                got, must_save = processor(src_id, src_rev, schema_id)
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
                    doc_model.create_schema_items(items)
                except DocumentSaveError, exc:
                    conflicts.extend(exc.infos)
                items = []
        if items:
            try:
                doc_model.create_schema_items(items)
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
                got, _ = processor(src_id, src_rev, schema_id)
                if got:
                    # don't bother batching when handling conflicts...
                    try:
                        doc_model.create_schema_items(got)
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
            got = self.processor.process_pending(pending)
            logger.debug("queue %r pending processing made %d items",
                         queue_id, len(got))
            if got:
                doc_model.create_schema_items(got)
                num_created += len(got)

        logger.debug("finished processing %r to %r - %d processed",
                     queue_id, last_seq, num_created)
        return num_created


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

    def process_pending(self, pending):
        new_items = []
        context = {'new_items': new_items}
        self._get_ext_env(context, None)
        func = self.ext.later_handler
        # Note we don't catch exceptions - failure stops this queue!
        try:
            func(pending)
        finally:
            self._release_ext_env()
        return new_items

    def __call__(self, src_id, src_rev, schema_id):
        """The "real" entry-point to this processor"""
        ext = self.ext
        if not ext.filter(src_id, src_rev, schema_id):
            return [], False

        dm = self.doc_model
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
            result = dm.open_view(key=key, reduce=False)
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
                            return (None, None)

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
                return (None, None)

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
        src_doc = dm.open_documents_by_id([src_id])[0]
        # Although we got this doc id directly from the _all_docs_by_seq view,
        # it is quite possible that the doc was deleted since we read that
        # view.  It could even have been updated - so if its not the exact
        # revision we need we just skip it - it will reappear later...
        if src_doc is None:
            logger.debug("skipping document %r - it's been deleted since we read the queue",
                         src_id)
            return (None, None)
        elif src_rev != None and src_doc['_rev'] != src_rev:
            logger.debug("skipping document %(_id)r - it's changed since we read the queue",
                         src_doc)
            return (None, None)

        # our caller should have filtered the list to only the schemas
        # our extensions cares about.
        assert ext.source_schemas is None or src_doc['rd_schema_id'] in ext.source_schemas

        # If the source of this document is yet to see a schema written by
        # a 'schema provider', skip calling extensions which depend on this
        # doc - we just wait for a 'provider' to be called, at which time
        # the source doc will again trigger us being called again.
        if not src_doc.get('rd_schema_provider'):
            logger.debug("skipping document %(_id)r - it has yet to see a schema provider",
                         src_doc)
            return (None, None)

        # Now process it
        new_items = []
        context = {'new_items': new_items}
        logger.debug("calling %r with doc %r, rev %s", ext_id,
                     src_doc['_id'], src_doc['_rev'])

        try:
            func = self._get_ext_env(context, src_doc)
            try:
                result = func(src_doc)
            finally:
                self._release_ext_env()
        except extenv.ProcessLaterException, exc:
            assert not new_items, "extensions can't do now and later!"
            # we still need to delete the older ones created last time.
            self._merge_new_with_previous(new_items, docs_previous)
            if new_items:
                self.doc_model.create_schema_items(new_items)
            raise
        except Exception:
            # handle_ext_failure may put error records into new_items.
            self._handle_ext_failure(sys.exc_info(), src_doc, new_items)
        else:
            if result is not None:
                # an extension returning a value implies they may be
                # confused?
                logger.warn("extension %r returned value %r which is ignored",
                            ext, result)


        self._merge_new_with_previous(new_items, docs_previous)
        # We try hard to batch writes; we earlier just checked to see if
        # only the same key was written, but that still failed.  Last
        # ditch attempt is to see if the extension made a query - if it
        # did, then it will probably query next time, and will probably
        # expect to see what it wrote last time
        must_save = 'did_query' in context
        logger.debug("extension %r generated %d new schemas (must_save=%s)",
                     ext_id, len(new_items), must_save)
        if not must_save:
            # must also save now if they wrote a key for another item.
            for i in new_items:
                logger.debug('new schema item %(rd_schema_id)r by'
                             ' %(rd_ext_id)r for key %(rd_key)r', i)
                if i['rd_key'] != src_doc['rd_key']:
                    must_save = True
                    break
        return (new_items, must_save)

    def _handle_ext_failure(self, exc_info, src_doc, new_items):
        # If a converter fails to
        # create a schema item, we can't just fail, or no later messages in the
        # DB will ever get processed!
        # So we write an 'error' schema and discard any it did manage to create
        # XXX - later we should use the extension's log, but for now
        # use out log but include the extension name.
        logger.warn("Extension %r failed to process document %r",
                    self.ext.id, src_doc['_id'], exc_info=exc_info)
        self.num_errors += 1
        if self.options.stop_on_error:
            logger.info("--stop-on-error specified - stopping queue")
            # Throw away any records emitted by *this* failure.
            new_items[:] = []
            raise exc_info[0], exc_info[1], exc_info[2]

        # and make the error record
        edoc = {'error_details': unicode(exc_info[1])}
        if new_items:
            logger.info("discarding %d items created before the failure",
                        len(new_items))
        new_items[:] = [{'rd_key' : src_doc['rd_key'],
                         'rd_source': [src_doc['_id'], src_doc['_rev']],
                         'rd_schema_id': 'rd.core.error',
                         'rd_ext_id' : self.ext.id,
                         'items' : edoc,
                         }]
