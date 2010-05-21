from raindrop.tests import TestCaseWithTestDB, FakeOptions
from raindrop.model import get_doc_model
from raindrop.proto import test as test_proto
from raindrop.sync import SyncConductor

import logging
logger = logging.getLogger(__name__)

class StubSMTP:
    def startSend(self, conductor, src_doc, out_doc):
        pass

class TestSyncing(TestCaseWithTestDB):
    no_sync_status_doc = True
    def make_config(self):
        config = TestCaseWithTestDB.make_config(self)
        # now add our smtp account
        acct = config.accounts['test_smtp'] = {}
        acct['proto'] = 'smtp'
        acct['username'] = 'test_raindrop@test.mozillamessaging.com'
        acct['id'] = 'smtp_test'
        return config

    def get_conductor(self):
        if self._conductor is None:
            self._conductor = SyncConductor(self.pipeline)
            self._conductor.initialize()
            # clobber the 'real' SMTP account with a stub.
            self._conductor.outgoing_handlers['rd.msg.outgoing.smtp'] = [StubSMTP()]
        return self._conductor

    def test_sync_state_doc(self, expected_num_syncs=1):
        self.makeAnotherTestMessage(None)
        self.ensure_pipeline_complete()
        # open the document with the sync state.
        wanted = ["raindrop", "sync-status"], 'rd.core.sync-status'
        si = self.doc_model.open_schemas([wanted])[0]
        self.failUnless(si)
        self.failUnlessEqual(si.get('new_items'), 1)
        self.failUnlessEqual(si.get('num_syncs'), expected_num_syncs)

    def test_sync_state_doc_twice(self):
        # make sure it works twice with the same conductor instance/db
        self.test_sync_state_doc()
        self.test_sync_state_doc(2)
