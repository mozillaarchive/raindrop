from pprint import pformat

from raindrop.tests.api import APITestCaseWithCorpus

class TestContacts(APITestCaseWithCorpus):
    idid = ['email', 'raindrop_test_user@mozillamessaging.com']    
    def setUpCorpus(self):
        return self.load_corpus('hand-rolled', 'sent-email-simple-reply')
    
    def test_identities_for_contact(self):
        # first we emit a contact record for our test identity.
        idrels = [(self.idid, 'email')]
        contact = {'displayName': 'test user'}
        self.call_api("model/contacts/create_identity_relationships",
                      relationships=idrels, contact_properties=contact)
        # get the contact ID for the identity.
        contacts = self.call_api("inflow/contacts/with_identity",
                                 id=['identity', self.idid])
        self.failUnlessEqual(len(contacts), 1, pformat(contacts))
        return contacts[0]

    def test_by_name(self):
        test_contact = self.test_identities_for_contact()
        contacts = self.call_api("inflow/contacts/by_name", startname="test user")
        self.failUnlessEqual(len(contacts), 1, pformat(contacts))
        cont = contacts[0]
        self.failUnlessEqual(cont['displayName'], "test user")
        self.failUnlessEqual(cont['id'], test_contact['id'])

    def test_convo_for_contact(self):
        # Get all convos for a contact
        contact = self.test_identities_for_contact()
        convos = self.call_api("inflow/conversations/contact", id=contact['id'], limit=2)
        self.failUnlessEqual(len(convos), 1, pformat(convos))
        conv = convos[0]
        self.failUnless(self.idid in conv['identities'], pformat(conv))
