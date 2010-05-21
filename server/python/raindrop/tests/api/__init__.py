# Helpers for API testers.

from urllib import urlencode

from raindrop.tests import TestCaseWithCorpus, TestCaseWithTestDB, json

class _APIMixin:
    def call_api(self, endpoint, _method="GET", _body=None, **kw):
        db = self.doc_model.db
        dbname = self.config.couches['local']['name']

        uri = "/%s/_api/%s" % (dbname, endpoint)
        if kw:
            opts = kw.copy()
            for name, val in opts.items():
                opts[name] = json.dumps(val)
            uri += "?" + urlencode(opts)
        if _body:
            _body = json.dumps(_body)
        return db._request(_method, uri, _body)

    
class APITestCaseWithCorpus(TestCaseWithCorpus, _APIMixin):
    def setUp(self):
        TestCaseWithCorpus.setUp(self)
        ndocs = self.setUpCorpus()
        self.failUnless(ndocs, "failed to load any corpus docs")
        self.ensure_pipeline_complete()
        # and reset our API so it reloads anything
        self.call_api("_reset")

    def tearDown(self):
        # calling _exit is primarily to ensure the process has closed all
        # connections, so the DB can be deleted on windows!
        self.call_api('_exit')
        TestCaseWithCorpus.tearDown(self)

    def setUpCorpus(self):
        return self.load_corpus('hand-rolled')
        

class APITestCase(TestCaseWithTestDB, _APIMixin):
    def setUp(self):
        TestCaseWithTestDB.setUp(self)
        # and reset our API so it reloads anything
        self.call_api("_reset")

    def tearDown(self):
        # calling _exit is primarily to ensure the process has closed all
        # connections, so the DB can be deleted on windows!
        self.call_api('_exit')
        TestCaseWithTestDB.tearDown(self)
