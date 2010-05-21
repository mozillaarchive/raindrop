# The raindrop test suite...
from __future__ import with_statement

import sys
import os
import glob
import base64
import time
from email import message_from_string

try:
    import unittest2 as unittest
except ImportError:
    import unittest

from raindrop import json
import raindrop.config
from raindrop.model import get_db, fab_db, get_doc_model
import raindrop.pipeline
from raindrop import bootstrap
from raindrop import sync
from raindrop.proto.imap import get_rdkey_for_email

import raindrop.proto
raindrop.proto.init_protocols(True)
test_proto = raindrop.proto.test

# all this logging stuff is misplaced...
import logging
logging.basicConfig()
if 'RAINDROP_LOG_LEVELS' in os.environ:
    # duplicated from run-raindrop...
    init_errors = []
    for val in os.environ['RAINDROP_LOG_LEVELS'].split(';'):
        try:
            name, level = val.split("=", 1)
        except ValueError:
            name = None
            level = val
        # convert a level name to a value.
        try:
            level = int(getattr(logging, level.upper()))
        except (ValueError, AttributeError):
            # not a level name from the logging module - maybe a literal.
            try:
                level = int(level)
            except ValueError:
                logging.getLogger().warn("Invalid log-level '%s' ignored" % (val,))
                continue
        l = logging.getLogger(name)
        l.setLevel(level)
    for e in init_errors:
        logging.getLogger().error(e)


class TestLogHandler(logging.Handler):
    def __init__(self, *args, **kw):
        logging.Handler.__init__(self, *args, **kw)
        self.ok_filters = []
        self.records = []

    def emit(self, record):
        for f in self.ok_filters:
            if f(record):
                break
        else:
            # no filters said OK
            self.records.append(record)

class FakeOptions:
    # XXX - get options from raindrop.opts...
    stop_on_error = False
    force = False
    protocols = None
    exts = None
    no_process = False
    repeat_after = 0
    folders = []
    max_age = 0
    continuous = False

class TestCase(unittest.TestCase):
    def resetRaindrop(self):
        import raindrop.extenv
        raindrop.extenv.reset_for_test_suite()
    
    def setUp(self):
        self.resetRaindrop()
        self.log_handler = TestLogHandler()
        # by default, WARNING or higher messages cause a test failure...
        filter = lambda record: record.levelno < logging.WARNING
        self.log_handler.ok_filters.append(filter)
        for l in [logging.getLogger(), logging.getLogger('raindrop')]:
            l.addHandler(self.log_handler)
            # this env-var means the developer wants to see the logs as it runs.
            if 'RAINDROP_LOG_LEVELS' not in os.environ:
                l.propagate = False
        return unittest.TestCase.setUp(self)

    def tearDown(self):
        l = logging.getLogger('raindrop')
        l.removeHandler(self.log_handler)
        parent_handler = l.parent.handlers[0]
        frecords = [parent_handler.format(r) for r in self.log_handler.records
                    if r.levelno >= logging.WARNING]
        if frecords:
            self.fail("unexpected log errors\n" + '\n'.join(frecords))
        return unittest.TestCase.tearDown(self)


class TestCaseWithTestDB(TestCase):
    """A test case that is setup to work with a temp database pre-populated
    with 'test protocol' raw messages.
    """
    def setUp(self):
        TestCase.setUp(self)
        self._conductor = None
        raindrop.config.CONFIG = None
        self.config = self.make_config()
        opts = self.get_options()
        self.doc_model = get_doc_model()
        self.pipeline = raindrop.pipeline.Pipeline(self.doc_model, opts)
        self.prepare_test_db(self.config)
        self.pipeline.initialize()

    def tearDown(self):
        if self.pipeline is not None:
            self.pipeline.finalize()
        TestCase.tearDown(self)

    def prepare_test_db(self, config):
        # change the name of the DB used.
        dbinfo = config.couches['local']
        # then blindly nuke it.
        db = get_db('local', dbinfo['name'])

        def del_non_test_accounts():
            # 'insert_default_docs' may have created an account (eg RSS) which
            # may get in the way of testing; nuke any which aren't in our
            # config.
            got = db.openView('raindrop!content!all', 'megaview',
                              key=['schema_id', 'rd.account'],
                              include_docs=True, reduce=False)
            wanted_ids = set(acct['id']
                             for acct in config.accounts.itervalues())
            to_del = [{'_id': r['doc']['_id'],
                       '_rev': r['doc']['_rev'],
                       '_deleted': True,
                       }
                      for r in got['rows'] if r['doc']['id'] not in wanted_ids]
            db.updateDocuments(to_del)

        db.deleteDB()
        fab_db()
        opts = self.get_options()
        bootstrap.install_views(opts, True)
        bootstrap.check_accounts(config)
        bootstrap.insert_default_docs(opts)
        del_non_test_accounts()
        if not getattr(self, 'no_sync_status_doc', False):
            # and make a dummy 'sync-status' doc so we don't attempt to send
            # welcome emails.
            items = {'new_items': 0,
                     'num_syncs': 2,
            }
            si = {'rd_key': ["raindrop", "sync-status"],
                  'rd_schema_id': 'rd.core.sync-status',
                  'rd_source': None,
                  'rd_ext_id': 'rd.core',
                  'items': items,
            }
            self.doc_model.create_schema_items([si])

    def failUnlessDocEqual(self, doc, expected_doc):
        # Generate a list of the properties of the document.
        # We ignore private properties of CouchDB (start with underscore)
        # and Raindrop (start with "rd_"), as we are only testing the public
        # properties generated by our extension.
        actual_properties = sorted([key for key in doc.keys()
                                        if not key.startswith('_')
                                        and not key.startswith('rd_')])

        expected_properties = sorted([key for key in expected_doc.keys()])

        # The document should have the expected properties.
        self.failUnlessEqual(actual_properties, expected_properties,
                             repr(doc['rd_key']) + ' properties')

        # The document's properties should have the expected values.
        for property in expected_doc:
            self.failUnlessEqual(doc[property], expected_doc[property],
                                 repr(doc['rd_key']) + '::' + property)

    def ensure_pipeline_complete(self, n_expected_errors=0):
        # later we will support *both* backlog and incoming at the
        # same time, but currently the test suite done one or the other...
        nerr = self.pipeline.start_processing(None)
        self.failUnlessEqual(n_expected_errors, nerr)

    def make_config(self):
        # change the name of the DB used.
        dbname = 'raindrop_test_suite'
        config = raindrop.config.init_config("~/." + dbname)
        dbinfo = config.couches['local']
        self.failUnlessEqual(dbinfo['name'], dbname)
        # We probably never want the user's accounts for auto testing.
        # setup a simple test one.
        config.accounts.clear()
        acct = config.accounts['test'] = {}
        acct['proto'] = 'test'
        acct['username'] = 'test'
        acct['num_test_docs'] = 0 # ignored!
        test_proto.test_num_test_docs = 0 # incremented later..
        acct['id'] = 'test'
        return config

    def get_options(self):
        opts = FakeOptions()
        return opts

    def get_conductor(self):
        if self._conductor is None:
            self._conductor = sync.get_conductor(self.pipeline)
        return self._conductor

    def makeAnotherTestMessage(self):
        # We need to reach into the impl to trick the test protocol
        test_proto.test_num_test_docs += 1
        c = self.get_conductor()
        c.sync(self.pipeline.options, wait=True)

class TestCaseWithCorpus(TestCaseWithTestDB):
    def prepare_corpus_environment(self, corpus_name):
        raindrop.config.CONFIG = None
        cd = self.get_corpus_dir(corpus_name)
        self.config = raindrop.config.init_config(os.path.join(cd, "raindrop"))
        # hack our couch server in
        dbinfo = self.config.couches['local']
        dbinfo['name'] = 'raindrop_test_suite'
        dbinfo['port'] = 5984
        opts = self.get_options()
        self.pipeline = raindrop.pipeline.Pipeline(self.doc_model, opts)
        self.prepare_test_db(self.config)
        self.pipeline.initialize()

    def rfc822_to_schema_item(self, fp):
        data = fp.read() # we need to use the data twice...
        msg_id = message_from_string(data)['message-id']
        si = {
                'rd_schema_id': 'rd.msg.rfc822',
                'rd_key': get_rdkey_for_email(msg_id),
                'rd_ext_id': 'proto.imap',
                'rd_source': None,
                'attachments' : {
                    'rfc822': {
                        'content_type': 'message',
                        'data': data,
                    }
                },
                'items' : {},
            }
        return si
        
    def get_corpus_dir(self, name):
        import raindrop.tests
        return os.path.join(raindrop.tests.__path__[0], "corpora", name)

    def gen_corpus_schema_items(self, corpus_name, item_spec="*"):
        cwd = os.getcwd()
        corpus_dir = self.get_corpus_dir(corpus_name)
        num = 0
        # We try and make life simple for people by auto-determining the
        # 'schema' for some well-known file types (eg, .rfc822.txt)
        pattern = "%s/%s.*" % (corpus_dir, item_spec)
        base_names = set()
        for filename in glob.iglob(pattern):
            try:
                path, name = os.path.split(filename)
                # don't use splitext - we want the *first* dot.
                first, _ = filename.split(".", 1)
                base = os.path.join(path, first)
            except ValueError:
                base = filename
            base_names.add(base)
        for basename in base_names:
            if basename.endswith('README') or basename.endswith('raindrop'):
                continue
            # .json files get first go - they may 'override' what we would
            # otherwise deduce.
            elif os.path.exists(basename + ".json"):
                filename = basename + ".json"
                with open(filename) as f:
                    try:
                        ob = json.load(f)
                    except ValueError, why:
                        self.fail("%r has invalid json: %r" % (filename, why))
                    # XXX - the below is probably broken but none of our
                    # JSON files provide them
                    assert '_attachments' not in ob, "please revisit this code!"
                    for name, data in ob.get('_attachments', {}).iteritems():
                        fname = os.path.join(corpus_dir, data['filename'])
                        with open(fname, 'rb') as attach_f:
                            data['data'] = attach_f.read()
                si = self.doc_model.doc_to_schema_item(ob)
            elif os.path.exists(basename + ".rfc822.txt"):
                # plain rfc822.txt file.
                with open(basename + ".rfc822.txt", 'rb') as f:
                    si = self.rfc822_to_schema_item(f)
            else:
                print "Don't know how to load '%s.*' into the corpus" % basename
                continue
            yield si
            num += 1
        self.failUnless(num, "failed to load any docs from %r matching %r" %
                        (corpus_name, item_spec))

    def init_corpus(self, corpus_name):
        self.prepare_corpus_environment(corpus_name)

    def load_corpus(self, corpus_name, corpus_spec="*"):
        self.init_corpus(corpus_name)
        items = [i for i in self.gen_corpus_schema_items(corpus_name, corpus_spec)]
        # this will do until we get lots...
        self.doc_model.create_schema_items(items)
        return len(items)
