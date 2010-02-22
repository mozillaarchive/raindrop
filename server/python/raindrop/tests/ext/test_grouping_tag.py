from twisted.internet import defer

from raindrop.tests import TestCaseWithCorpus


class TestSimpleCorpus(TestCaseWithCorpus):
    @defer.inlineCallbacks
    def test_simple_notification(self):
        ndocs = yield self.load_corpus("hand-rolled", "sent-email-simple-reply")
        _ = yield self.ensure_pipeline_complete()

        # open all grouping-tag schemas - should be only 1
        key = ["rd.core.content", "schema_id", "rd.msg.grouping-tag"]
        result = yield self.doc_model.open_view(key=key, reduce=False,
                                                include_docs=True)
        # Check that grouping-tag specifies a tag for us
        rows = result['rows']
        self.failUnlessEqual(len(rows), 1)
        ex_tag = 'identity-email-raindrop_test_user@mozillamessaging.com'
        self.failUnlessEqual(rows[0]['doc']['tag'], ex_tag)
        # The back-end boostrap process has arranged for "our identities" to
        # be associated with the inflow grouping.
        ex_grouping_key = ['display-group', 'inflow']
        key = ["rd.core.content", "schema_id", "rd.grouping.summary"]
        result = yield self.doc_model.open_view(key=key, reduce=False,
                                                include_docs=True)
        rows = result['rows']
        self.failUnlessEqual(len(rows), 1)
        self.failUnlessEqual(rows[0]['doc']['rd_key'], ex_grouping_key)

    @defer.inlineCallbacks
    def test_bulk_sender(self):
        # first run the extension.
        _ = yield self.test_simple_notification()

        # now create a schema item indicating this sender is a 'bulk sender'
        rdkey = ['identity', ['email', 'raindrop_test_recip@mozillamessaging.com']]
        si = {
            'rd_key': rdkey,
            'rd_schema_id': 'rd.identity.sender-flags',
            'rd_ext_id': 'rd.testsuite',
            'items' : {
                'bulk': 'true',
            }
        }
        _ = yield self.doc_model.create_schema_items([si])
        _ = yield self.ensure_pipeline_complete()

        # open all grouping-tag schemas - should be only 1
        key = ["rd.core.content", "schema_id", "rd.msg.grouping-tag"]
        result = yield self.doc_model.open_view(key=key, reduce=False,
                                                include_docs=True)
        # Check the grouping-tag schema for the identity caused the message
        # to be reported as the *senders* tag
        rows = result['rows']
        self.failUnlessEqual(len(rows), 1)
        self.failUnlessEqual(rows[0]['doc']['tag'],
                             'identity-email-raindrop_test_recip@mozillamessaging.com')
        # And that we have a grouping-summary for this sender (ie, it is no
        # longer in the 'inflow' group.)
        ex_grouping_key = ['identity', ['email', 'raindrop_test_recip@mozillamessaging.com']]
        key = ["rd.core.content", "schema_id", "rd.grouping.summary"]
        result = yield self.doc_model.open_view(key=key, reduce=False,
                                                include_docs=True)
        rows = result['rows']
        self.failUnlessEqual(len(rows), 1)
        self.failUnlessEqual(rows[0]['doc']['rd_key'], ex_grouping_key)


class TestSimpleCorpusBacklog(TestSimpleCorpus):
    use_incoming_processor = not TestSimpleCorpus.use_incoming_processor
