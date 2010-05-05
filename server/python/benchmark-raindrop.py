# ***** BEGIN LICENSE BLOCK *****
# * Version: MPL 1.1
# *
# * The contents of this file are subject to the Mozilla Public License Version
# * 1.1 (the "License"); you may not use this file except in compliance with
# * the License. You may obtain a copy of the License at
# * http://www.mozilla.org/MPL/
# *
# * Software distributed under the License is distributed on an "AS IS" basis,
# * WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# * for the specific language governing rights and limitations under the
# * License.
# *
# * The Original Code is Raindrop.
# *
# * The Initial Developer of the Original Code is
# * Mozilla Messaging, Inc..
# * Portions created by the Initial Developer are Copyright (C) 2009
# * the Initial Developer. All Rights Reserved.
# *
# * Contributor(s):
# *

# A very hacky script to try and get some "benchmarks" for raindrop's backend.
# The intent is that this script can help you determine the relative
# performance cost or benefit of particular strategies.

from __future__ import division

import os
import time
import optparse
try:
    import simplejson as json
except ImportError:
    import json

from raindrop.config import get_config
from raindrop.proto.imap import MAX_MESSAGES_PER_FETCH

from raindrop.tests import TestCaseWithCorpus, FakeOptions
from raindrop.config import get_config

def format_num_bytes(nbytes):
    KB = 1000
    MB = KB * 1000
    GB = MB * 1000
    for (what, desc) in ((GB, 'GB'), (MB, 'MB'), (KB, 'KB')):
        if nbytes > what:
            return "%.3g%s" % ((nbytes/what), desc)
    return "%sB" % nbytes

class CorpusHelper(TestCaseWithCorpus):
    def __init__(self, opts):
        self.opt_dict = opts
    def get_options(self):
        opts = FakeOptions()
        for name, val in self.opt_dict.iteritems():
            setattr(opts, name, val)
        return opts


def make_corpus_helper(opts, **pipeline_opts):
    tc = CorpusHelper(pipeline_opts)
    tc.setUp()
    if opts.enron_dir:
        tc.init_corpus('enron')
    return tc


def gen_corpus_items(testcase, opts):
    # A generator of *lists* of schema items.  Uses *lists* of schema
    # items to closer approximate an IMAP server where each folder has
    # an arbitary number of items and these are delivered in similar chunks.
    if opts.enron_dir:
        for root, dirs, files in os.walk(opts.enron_dir):
            this = []
            for file in files:
                fq = os.path.join(root, file)
                this.append(testcase.rfc822_to_schema_item(open(fq, "rb")))
            if this:
                yield this
    else:
        # for now, just use the hand-rolled corpus
        for si in testcase.gen_corpus_schema_items('hand-rolled'):
            yield [si]


def gen_batched_corpus_items(testcase, opts):
    g = gen_corpus_items(testcase, opts)
    for sub_batch in gen_corpus_items(testcase, opts):
        this = []
        while sub_batch:
            this.append(sub_batch.pop(0))
            if len(this) > MAX_MESSAGES_PER_FETCH:
                yield this
                this = []
        if this:
            yield this
            this = []


def load_corpus(testcase, opts):
    num = 0
    for batch in gen_batched_corpus_items(testcase, opts):
        testcase.doc_model.create_schema_items(batch)
        num += len(batch)
    return num


def load_and_sync(testcase, opts):
    num = 0
    for batch in gen_batched_corpus_items(testcase, opts):
        testcase.doc_model.create_schema_items(batch)
        testcase.ensure_pipeline_complete()
        num += len(batch)
    return num


def timeit(func, *args):
    start = time.clock()
    ret = func(*args)
    took = time.clock()-start
    return ret, took


def profileit(func, *args):
    import cProfile
    profiler = cProfile.Profile()
    ret = profiler.runcall(func, *args)
    profiler.print_stats(2)
    return ret, 0


def report_db_state(db, opts):
    info = db.infoDB()
    print "DB has %(doc_count)d docs at seq %(update_seq)d in %(disk_size)d bytes" % info
    if opts.couch_dir:
        # report what we find on disk about couch.
        dbname = 'raindrop_test_suite' # hardcoded by test-suite helpers we abuse.
        dbsize = os.path.getsize(os.path.join(opts.couch_dir, dbname + ".couch"))
        # and walk looking for view files.
        vsize = 0
        for root, dirs, files in os.walk(os.path.join(opts.couch_dir, ".%s_design" % dbname)):
            vsize += sum(os.path.getsize(os.path.join(root, name)) for name in files)
        ratio = vsize / dbsize
        nb = format_num_bytes
        print "DB on disk is %s, views are %s (%s total, ratio 1:%0.2g)" % \
             (nb(dbsize), nb(vsize), nb(dbsize+vsize), ratio)

    
def run_timings_async(opts):
    tc = make_corpus_helper(opts, no_process=True)
    print "Starting asyncronous loading and processing..."
    ndocs, avg = timeit(load_corpus, tc, opts)
    print "Loaded %d documents in %.3f" % (ndocs, avg)
    # now do a 'process' on one single extension.
    tc.pipeline.options.exts = ['rd.ext.core.msg-rfc-to-email']
    _, avg = timeit(tc.pipeline.start_processing, None)
    print "Ran 1 extension in %.3f" % (avg)
    # now do a few in (hopefully) parallel
    tc.pipeline.options.exts = ['rd.ext.core.msg-email-to-body',
                                'rd.ext.core.msg-email-to-mailinglist',
                                'rd.ext.core.msg-email-to-grouping-tag',
                                'rd.ext.core.msg-body-to-quoted',
                                'rd.ext.core.msg-body-quoted-to-hyperlink',
                                ]
    _, avg = timeit(tc.pipeline.start_processing, None)
    print "Ran %d extensions in %.3f" % (len(tc.pipeline.options.exts), avg)
    # now the 'rest'
    tc.pipeline.options.exts = None
    _, avg = timeit(tc.pipeline.start_processing, None)
    print "Ran remaining extensions in %.3f" % (avg,)
    report_db_state(tc.pipeline.doc_model.db, opts)
    # try unprocess then process_backlog
    _, avg = timeit(tc.pipeline.unprocess)
    print "Unprocessed in %.3f" % (avg,)
    _, avg = timeit(tc.pipeline.start_processing, None)
    print "re-processed in %.3f" % (avg,)
    report_db_state(tc.pipeline.doc_model.db, opts)
    tc.tearDown()


def run_timings_sync(opts):
    tc = make_corpus_helper(opts)
    print "Starting syncronous loading..."
    ndocs, avg = timeit(load_and_sync, tc, opts)
    print "Loaded and processed %d documents in %.3f" % (ndocs, avg)
    report_db_state(tc.pipeline.doc_model.db, opts)
    tc.tearDown()


def run_api_timings(opts):
    import httplib
    from urllib import urlencode    
    couch = get_config().couches['local']
    c = httplib.HTTPConnection(couch['host'], couch['port'])
    tpath = '/%s/_api/inflow/%s'
    
    def make_req(path):
        c.request('GET', path)
        return c.getresponse()

    def do_timings(api, desc=None, **kw):
        api_path = tpath % (couch['name'], api)
        if kw:
            opts = kw.copy()
            for opt_name in opts:
                opts[opt_name] = json.dumps(opts[opt_name])
            api_path += "?" + urlencode(opts)
        resp, reqt = timeit(make_req, api_path)
        dat, respt = timeit(resp.read)
        if not desc:
            desc = api
        if resp.status != 200:
            print "*** api %r failed with %s: %s" % (desc, resp.status, resp.reason)
        print "Made '%s' API request in %.3f, read response in %.3f (size was %s)" \
              % (desc, reqt, respt, format_num_bytes(len(dat)))
        return json.loads(dat)

    result = do_timings("grouping/summary")
    for gs in result:
        title = gs.get('title') or gs['rd_key']
        do_timings("conversations/in_groups", "in_groups: " + str(title),
                   limit=60, message_limit=2, keys=[gs['rd_key']])


def main():
    parser = optparse.OptionParser()
    parser.add_option("", "--enron-dir",
                      help=
"""Directory root of an enron-style corpus to use.  You almost certainly do
not want to specify the root of the enron corpus - specify one of the
child (leaf) directories.  For example {root}/beck-s/eurpoe holds 166
documents.""")
    parser.add_option("", "--couch-dir",
                      help=
"""Directory where the couchdb database files are stored.  If specified
the size on disk of the DB and views will be reported.""")
    parser.add_option("", "--skip-sync", action="store_true",
                      help="don't benchmark sync processing")
    parser.add_option("", "--skip-async", action="store_true",
                      help="don't benchmark async processing")
    parser.add_option("", "--skip-api", action="store_true",
                      help="don't benchmark api processing")
    opts, args = parser.parse_args()

    if not opts.skip_async:
        run_timings_async(opts)
    if not opts.skip_sync:
        run_timings_sync(opts)
    if not opts.skip_api:
        run_api_sync(opts)


if __name__ == "__main__":
    main()
