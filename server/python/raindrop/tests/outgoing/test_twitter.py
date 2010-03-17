from twisted.internet import defer
from raindrop.tests import TestCaseWithTestDB
from raindrop.sync import SyncConductor
from raindrop.proc import base


class StubTwitter(base.AccountBase):
    def __init__(self, doc_model, details, testcase):
        base.AccountBase.__init__(self, doc_model, details)
        self.testcase = testcase
        self.num_sends = 0

    @defer.inlineCallbacks
    def startSend(self, conductor, src_doc, out_doc):
        self.testcase.failUnlessEqual(src_doc['outgoing_state'], 'outgoing')
        self.testcase.failUnlessEqual(src_doc['body'], 'this is a test tweet')

        # Here we record the fact we have attempted a send and
        # save the state back now - this should cause conflict errors if we
        # accidently have 2 processes trying to send the same message.
        _ = yield self._update_sent_state(src_doc, 'sending')
        # now is when we would do the actual twitter send.
        _ = yield self._update_sent_state(src_doc, 'sent')
        # or for failure...
        # reason = (non_200_status_code, status_message) for example
        #_ = yield self._update_sent_state(src_doc, 'error',
        #                                  reason, "message for user",
        #                                  # reset to 'outgoing' if temp error.
        #                                  # or set to 'error' if permanent.
        #                                  outgoing_state='outgoing')
        self.num_sends += 1


# This test uses a 'stub' twitter account - it doesn't attempt to make
# any connections to anything, but instead just check the twitter acct
# is called with appropriate data.
class TestSendStub(TestCaseWithTestDB):
    def make_config(self):
        config = TestCaseWithTestDB.make_config(self)
        # now add our twitter account
        acct = config.accounts['test_twitter'] = {}
        acct['id'] = 'twitter'
        acct['proto'] = 'twitter'
        acct['username'] = 'raindrop_twitter_test'
        return config

    def get_conductor(self):
        if self._conductor is None:
            details = self.config.accounts['test_twitter']
            self.stub_twitter = StubTwitter(self.doc_model, details, self)
            self._conductor = SyncConductor(self.pipeline)
            self._conductor.initialize()
            # clobber the 'real' twitter account with out stub.
            self._conductor.outgoing_handlers['rd.msg.outgoing.tweet'] = [self.stub_twitter]
        return defer.succeed(self._conductor)

    @defer.inlineCallbacks
    def test_simple(self):
        self.get_conductor()
        result = yield self.doc_model.create_schema_items([
                    {'rd_key': ['test', 'tweet_test'],
                     'rd_ext_id': 'testsuite',
                     'rd_schema_id': 'rd.msg.outgoing.tweet',
                     'items': {
                        'outgoing_state': 'outgoing',
                        'body': 'this is a test tweet',
                        'in_reply_to' : None,
                        # more fields??
                     },
                    }])

        _ = yield self.ensure_pipeline_complete()
        self.failUnlessEqual(self.stub_twitter.num_sends, 1)
