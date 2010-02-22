from pprint import pformat
from twisted.internet import defer, reactor

from raindrop.tests import TestCaseWithCorpus


class TestSimpleCorpus(TestCaseWithCorpus):
    @defer.inlineCallbacks
    def put_docs(self, corpus_name, corpus_spec="*", expected=None):
        items = [d for d in self.gen_corpus_schema_items(corpus_name, corpus_spec)]
        if expected is not None:
            self.failUnlessEqual(len(items), expected)
        _ = yield self.doc_model.create_schema_items(items)
        _ = yield self.ensure_pipeline_complete()

    @defer.inlineCallbacks
    def test_groups_single(self):
        # Initialize the corpus & database.
        yield self.init_corpus('hand-rolled')

        # Process a single item - should get its own convo
        yield self.put_docs('hand-rolled', 'sent-email-simple-reply', 1)

        msgid = ['email', '78cb2eb5dbc74cdd9691dcfdb266d1b9@something']
        body_schema = (yield self.doc_model.open_schemas([(msgid, 'rd.msg.body')]))[0]
        # should be one 'rd.convo.summary' doc in the DB.
        key = ['rd.core.content', 'schema_id', 'rd.conv.summary']
        result = yield self.doc_model.open_view(key=key, reduce=False,
                                                include_docs=True)
        rows = result['rows']
        self.failUnlessEqual(len(rows), 1, pformat(rows))
        self.failUnlessEqual(rows[0]['doc']['rd_schema_id'], 'rd.conv.summary')
        conv_id = rows[0]['doc']['rd_key']

        # should also be exactly 1 'grouping summary'
        key = ['rd.core.content', 'schema_id', 'rd.grouping.summary']
        result = yield self.doc_model.open_view(key=key, reduce=False,
                                                include_docs=True)
        rows = result['rows']
        self.failUnlessEqual(len(rows), 1, pformat(rows))
        self.failUnlessEqual(rows[0]['doc']['rd_schema_id'], 'rd.grouping.summary')
        doc_sum = rows[0]['doc']
        expected_doc = {
            'unread' : [conv_id],
            'num_unread': 1,
        }
        self.failUnlessDocEqual(doc_sum, expected_doc)

    @defer.inlineCallbacks
    def test_groups_ungrouped(self):
        _ = yield self.init_corpus('hand-rolled')
        msg = """\
Delivered-To: raindrop_test_user@mozillamessaging.com
From: someone@somewhere.com
Date: Sat, 21 Jul 2009 12:13:14 -0000
Message-Id: <1234@something>

Hello everyone
"""
        si = {'rd_key': ['email', '1234@something'],
              'rd_schema_id': 'rd.msg.rfc822',
              'rd_source' : None,
              'rd_ext_id': 'rd.testsuite',
              'items': {},
              'attachments' : {
                    'rfc822': {
                        'data': msg,
                    }
              }
              }
        _ = yield self.doc_model.create_schema_items([si])
        _ = yield self.ensure_pipeline_complete()
        # should also be exactly 1 'grouping summary' for this unknown sender
        rd_key = ['identity', ['email', 'someone@somewhere.com']]
        docs = yield self.doc_model.open_schemas([(rd_key, 'rd.grouping.summary')])
        doc = docs[0]
        self.failUnless(doc, 'no summary group')
        self.failUnlessEqual(doc['num_unread'], 1)

class TestSimpleCorpusBacklog(TestSimpleCorpus):
    use_incoming_processor = not TestSimpleCorpus.use_incoming_processor
