from twisted.internet import defer

from raindrop.tests import TestCaseWithCorpus
from raindrop.proto import test as test_proto

class TestSimpleCorpus(TestCaseWithCorpus):
    @defer.inlineCallbacks
    def get_num_with_key(self, key, docId='raindrop!content!all', viewId='megaview'):
        result = yield self.doc_model.open_view(docId, viewId, key=key)
        rows = result['rows']
        if len(rows)==0:
            defer.returnValue(0)
        # XXX - hackery!
        # If 'id' is in a row, then it must not be a reduce view
        if 'id' in rows[0]:
            defer.returnValue(len(rows))
        else:
            # a reduce view - count is in  'value'
            self.failUnlessEqual(len(rows), 1)
            defer.returnValue(rows[0]['value'])

    @defer.inlineCallbacks
    def check_all_worked(self, ndocs):
        # now some sanity checks on the processing.
        # should be zero error records.
        num = yield self.get_num_with_key(
                ["rd.core.content", "schema_id", "rd.core.error"])
        self.failUnlessEqual(num, 0)
        # should be one rd.msg.body schema for every item in the corpus.
        num = yield self.get_num_with_key(
                    ["rd.core.content", "schema_id", "rd.msg.body"])
        self.failUnlessEqual(num, ndocs)

        # There is at least one message from and to our test identity, and
        # from our 'test recipient'
        for iid in (['email', 'raindrop_test_user@mozillamessaging.com'],
                    ['email', 'raindrop_test_recip@mozillamessaging.com'],
                   ):
            for what in ('from', 'to'):
                num = yield self.get_num_with_key(
                            [what, iid],
                            'raindrop!content!tests', viewId='msg_body_recipients')
                self.failUnless(num, (what, iid))
        for name in ['Raindrop Test User', 'Raindrop Test Recipient']:
            for what in ('from_display', 'to_display'):
                num = yield self.get_num_with_key(
                            [what, name],
                            'raindrop!content!tests', viewId='msg_body_recipients')
                self.failUnless(num, (what, name))

    @defer.inlineCallbacks
    def test_async(self):
        ndocs = yield self.load_corpus("hand-rolled")
        self.failUnless(ndocs, "failed to load any corpus docs")
        _ = yield self.ensure_pipeline_complete()
        _ = yield self.check_all_worked(ndocs)


# Test that given our collection of malformed messages, none of the extensions
# fail.  They might log warnings and otherwise skip the processing of a
# message, but nothing should fail.
class TestMalformedCorpus(TestCaseWithCorpus):
    @defer.inlineCallbacks
    def get_num_with_key(self, key):
        result = yield self.doc_model.open_view(key=key)
        rows = result['rows']
        if len(rows)==0:
            defer.returnValue(0)
        self.failUnlessEqual(len(rows), 1)
        defer.returnValue(rows[0]['value'])

    @defer.inlineCallbacks
    def check_all_worked(self, ndocs):
        # now some sanity checks on the processing.
        # should be zero error records.
        num = yield self.get_num_with_key(
                ["rd.core.content", "schema_id", "rd.core.error"])
        self.failUnlessEqual(num, 0)

    @defer.inlineCallbacks
    def test_async(self):
        ndocs = yield self.load_corpus("malformed")
        self.failUnless(ndocs, "failed to load any corpus docs")
        _ = yield self.ensure_pipeline_complete()
        _ = yield self.check_all_worked(ndocs)
