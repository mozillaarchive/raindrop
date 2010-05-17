from pprint import pformat
from raindrop.tests.api import APITestCaseWithCorpus

class TestAttachments(APITestCaseWithCorpus):
    def setUpCorpus(self):
        return self.load_corpus('hand-rolled', 'quoted-hyperlinks')

    def test_attach_links(self):
        msgid = ['email', '20090514020118.C33915681F2D@example2.com']
        # find the convo ID
        key = ['key-schema_id', [msgid, 'rd.msg.conversation']]
        result = self.doc_model.open_view(key=key, reduce=False,
                                          include_docs=True)
        # should be 1 convo
        self.failUnlessEqual(len(result['rows']), 1)
        conv_id = None
        for row in result['rows']:
            if conv_id is None:
                conv_id = row['doc']['conversation_id']
            else:
                self.failUnlessEqual(conv_id, row['doc']['conversation_id'])

        conv = self.call_api("inflow/conversations/by_id", key=conv_id)
        # first should should be ours.
        self.failUnlessEqual(len(conv['messages']), 1, pformat(conv))
        msg = conv['messages'][0]
        self.failUnlessEqual(msg['id'], msgid, pformat(msg))
        # build the set of attachments and schemas we want
        a_by_id = {}
        sids = set()
        for attach in msg['attachments']:
            a_by_id[self.doc_model.hashable_key(attach['id'])] = attach
            for sid in attach['schemas']:
                sids.add(sid)
        result = self.call_api("inflow/message/attachments",
                               keys=a_by_id.keys(), schemas=list(sids))
        # should be exactly as many result objects as keys
        self.failUnlessEqual(len(result), len(a_by_id), pformat(result))
        # check that every attachment has all schemas.
        for ret_attach in result:
            summary_attach = a_by_id[self.doc_model.hashable_key(ret_attach['id'])]
            self.failUnlessEqual(summary_attach['schemas'].keys(), ret_attach['schemas'].keys())
            # and every schema should have values.
            for schema in ret_attach['schemas'].itervalues():
                self.failUnless(schema)
        # and for now, this probably means we worked!
