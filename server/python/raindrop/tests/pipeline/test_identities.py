# Test the 'identity spawner pipeline'
from pprint import pformat

from raindrop.tests import TestCaseWithTestDB, FakeOptions
from raindrop.model import get_doc_model
from raindrop.proto import test as test_proto
from raindrop import pipeline

import logging
logger = logging.getLogger(__name__)

class TestIDPipelineBase(TestCaseWithTestDB):
    def get_options(self):
        ret = TestCaseWithTestDB.get_options(self)
        ret.exts = ['rd.test.core.test_converter']
        return ret

    def process_doc(self, emit_common_ids=True):
        test_proto.set_test_options(emit_identities=True,
                                    emit_common_identities=emit_common_ids)
        self.makeAnotherTestMessage()
        self.ensure_pipeline_complete()


class TestIDPipeline(TestIDPipelineBase):
    # Test extracting identities and contacts test protocol messages
    # work as expected.
    def verifyCounts(self, contact_count, identity_count):
        # First determine the contact ID.
        key = ['schema_id', 'rd.contact']
        result = get_doc_model().open_view(key=key, reduce=False)
        self.failUnlessEqual(len(result['rows']), contact_count, pformat(result))

        # each identity should have got 2 schema instances.
        keys = [['schema_id', 'rd.identity.exists'],
                ['schema_id', 'rd.identity.contacts'],
               ]

        result = get_doc_model().open_view(keys=keys, reduce=False)
        self.failUnlessEqual(len(result['rows']), identity_count*2, pformat(result))

    def test_one_testmsg(self):
        # When processing a single test message we end up with 2 identies
        # both associated with the same contact

        result = self.process_doc()
        dm = get_doc_model()
        # First determine the contact ID.
        key = ['schema_id', 'rd.contact']
        result = dm.open_view(key=key, reduce=False, include_docs=True)

        rows = result['rows']
        # Should be exactly 1 record with a 'contact' schema.
        self.failUnlessEqual(len(rows), 1, str(rows))
        key_type, cid = rows[0]['doc']['rd_key']
        self.failUnlessEqual(key_type, 'contact')

        # should be exact 2 rd.identity.contacts records, each pointing
        # at my contact.
        key = ['schema_id', 'rd.identity.contacts']
        result = dm.open_view(key=key, reduce=False, include_docs=True)
        rows = result['rows']
        self.failUnlessEqual(len(rows), 2, str(rows))
        docs = [r['doc'] for r in rows]
        for doc in docs:
            contacts = doc['contacts']
            self.failUnlessEqual(len(contacts), 1, contacts)
            this_id, this_rel = contacts[0]
            self.failUnlessEqual(this_id, cid)
            self.failUnless(this_rel in ['personal', 'public'], this_rel)
        # and that will do!

    def test_common_idid(self):
        # Here we process 2 test messages which result in both messages
        # having an identity in common and one that is unique.  When we
        # process the second message we should notice the shared identity_id
        # is already associated with the contact we created first time round,
        # with the end result we still end up with a single contact, but now
        # have *three* identities for him
        self.test_one_testmsg()
        result = self.process_doc()
        # First determine the contact ID.
        key = ['schema_id', 'rd.contact']
        result = get_doc_model().open_view(key=key, reduce=False,
                                           include_docs=True)

        rows = result['rows']
        # Should be exactly 1 record with a 'contact' schema.
        self.failUnlessEqual(len(rows), 1, str(rows))
        key_type, cid = rows[0]['doc']['rd_key']
        self.failUnlessEqual(key_type, 'contact')

        # should be exact 3 rd.identity.contacts records, each pointing
        # at my contact.
        key = ['schema_id', 'rd.identity.contacts']
        result = get_doc_model().open_view(key=key,
                                           reduce=False,
                                           include_docs=True)

        rows = result['rows']
        self.failUnlessEqual(len(rows), 3, str(rows))
        docs = [r['doc'] for r in rows]
        for doc in docs:
            contacts = doc['contacts']
            self.failUnlessEqual(len(contacts), 1, contacts)
            this_id, this_rel = contacts[0]
            self.failUnlessEqual(this_id, cid)
            self.failUnless(this_rel in ['personal', 'public'], this_rel)

        self.verifyCounts(1, 3)

    def test_unique_idid(self):
        # Here we process 2 test messages but none of the messages emit a
        # common identity ID.  The end result is we end up with 2 contacts;
        # one with 2 identities (from reusing test_one_testmsg), then a second
        # contact with only a single identity
        self.test_one_testmsg()
        result = self.process_doc(False)
        # First determine the 2 contact IDs.
        key = ['schema_id', 'rd.contact']
        result = get_doc_model().open_view(key=key, reduce=False,
                                           include_docs=True)

        rows = result['rows']
        # Should be exactly 2 records with a 'contact' schema.
        self.failUnlessEqual(len(rows), 2, pformat(rows))
        key_type, cid1 = rows[0]['doc']['rd_key']
        self.failUnlessEqual(key_type, 'contact')
        key_type, cid2 = rows[1]['doc']['rd_key']
        self.failUnlessEqual(key_type, 'contact')

        # should be exact 3 rd.identity.contacts records, each pointing
        # at my contact.
        key = ['schema_id', 'rd.identity.contacts']
        result = get_doc_model().open_view(key=key, reduce=False,
                                           include_docs=True)

        rows = result['rows']
        self.failUnlessEqual(len(rows), 3, str(rows))
        docs = [r['doc'] for r in rows]
        for doc in docs:
            contacts = doc['contacts']
            self.failUnlessEqual(len(contacts), 1, contacts)
            this_id, this_rel = contacts[0]
            self.failUnless(this_id in [cid1, cid2])
            self.failUnless(this_rel in ['personal', 'public'], this_rel)

        self.verifyCounts(2, 3)

    def test_common_displayname(self):
        # Here we process 2 identities, each with a different email address
        # but both with a common display-name.  We should end up with a single
        # contact with both identities.
        si = {'rd_key': ['identity', ['email', 'test1@test.com']],
              'rd_schema_id': 'rd.identity.exists',
              'rd_source' : None,
              'rd_ext_id': 'rd.testsuite',
              'items': None,
              }
        self.doc_model.create_schema_items([si])
        # and make a contact for this address.
        contact = {'displayName': 'test user'}
        from raindrop import extenv
        idrels = [(si['rd_key'][1], 'email')]
        items = list(extenv.items_from_related_identities(self.doc_model,
                                                          idrels, contact,
                                                          'rd.testsuite'))
        self.doc_model.create_schema_items(items)
        # should be one contact with one identity.
        self.verifyCounts(1, 1)
        # now create the second identity with the same display name.
        si = {'rd_key': ['identity', ['email', 'test2@test.com']],
              'rd_schema_id': 'rd.identity.exists',
              'rd_source' : None,
              'rd_ext_id': 'rd.testsuite',
              'items': None,
              }
        self.doc_model.create_schema_items([si])
        idrels = [(si['rd_key'][1], 'email')]
        items = list(extenv.items_from_related_identities(self.doc_model,
                                                          idrels, contact,
                                                          'rd.testsuite'))
        self.doc_model.create_schema_items(items)
        # should be one contact with two identities.
        self.verifyCounts(1, 2)
