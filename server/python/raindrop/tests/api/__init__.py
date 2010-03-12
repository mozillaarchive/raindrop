# Helpers for API testers.

from urllib import urlencode

from twisted.internet import defer

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
        if _method == 'GET':
            self.failUnlessEqual(_body, None)
            return db.get(uri
                ).addCallback(db.parseResult)
        elif _method == 'POST':
            return db.postob(uri, _body
                ).addCallback(db.parseResult)

    
class APITestCaseWithCorpus(TestCaseWithCorpus, _APIMixin):
    @defer.inlineCallbacks
    def setUp(self):
        _ = yield TestCaseWithCorpus.setUp(self)
        ndocs = yield self.load_corpus('hand-rolled')
        self.failUnless(ndocs, "failed to load any corpus docs")
        _ = yield self.ensure_pipeline_complete()
        # and reset our API so it reloads anything
        _ = yield self.call_api("_reset")

class APITestCase(TestCaseWithTestDB, _APIMixin):
    @defer.inlineCallbacks
    def setUp(self):
        _ = yield TestCaseWithTestDB.setUp(self)
        # and reset our API so it reloads anything
        _ = yield self.call_api("_reset")
