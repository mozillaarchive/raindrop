from pprint import pformat
import rfc822
from raindrop.tests.api import APITestCase, APITestCaseWithCorpus

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
        result = self.call_api("inflow/attachments/by_id",
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


# tests which don't use a corpus but instead introduce test messages
# manually.
class TestAttachmentsNonSummary(APITestCase):
    msg_template = """\
Delivered-To: raindrop_test_user@mozillamessaging.com
From: Raindrop Test User <Raindrop_test_user@mozillamessaging.com>
To: Raindrop Test Recipient <Raindrop_test_recip@mozillamessaging.com>
Date: %(date)s
Message-Id: %(mid)s
References: %(refs)s

Hello - please see http://www.mozillamessaging.com
"""

    def get_message_schema_item(self, msgid, refs):
        args = {'mid': '<'+msgid+'>',
                'refs': ' '.join(['<'+ref+'>' for ref in refs]),
                'date': rfc822.formatdate(),
                }
        src = self.msg_template % args
        si = {'rd_key': ['email', msgid],
              'rd_schema_id': 'rd.msg.rfc822',
              'rd_source' : None,
              'rd_ext_id': 'rd.testsuite',
              'items': {},
              'attachments' : {
                    'rfc822': {
                        'data': src
                    }
              }
        }
        return si

    def make_test_convo(self):
        # create one convo with 10 messages.
        items = [self.get_message_schema_item("0@something.com", [])]
        for i in range(1, 10):
            items.append(self.get_message_schema_item("%d@something.com" % i,
                                                      ["0@something.com"]))
        self.doc_model.create_schema_items(items)
        self.ensure_pipeline_complete()
        # should be 1 convo.
        key = ['schema_id', 'rd.conv.summary']
        result = self.doc_model.open_view(key=key, reduce=False,
                                          include_docs=True)
        self.failUnlessEqual(len(result['rows']), 1)
        cid = result['rows'][0]['doc']['rd_key']
        return cid

    def test_attach(self):
        conv_id = self.make_test_convo()
        result = self.call_api("inflow/conversations/by_id",
                               key=conv_id, message_limit=10)
        self.failUnlessEqual(len(result['messages']), 10)
        # every single message should have an 'attachments' elt - some came
        # from the convo summary while some were fetched by the API.
        for msg in result['messages']:
            self.failUnless('attachments' in msg, pformat(result))
            attachments = msg['attachments']
            # should be 1 attachment per message
            self.failUnlessEqual(len(attachments), 1, pformat(attachments))
            # the attachment summary should have the 'link' schema
            self.failUnless('rd.attach.link' in attachments[0]['schemas'], pformat(attachments))
