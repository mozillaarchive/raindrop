from pprint import pformat

from raindrop.tests import TestCaseWithCorpus, TestCaseWithTestDB


class TestSimpleCorpus(TestCaseWithCorpus):
    def put_docs(self, corpus_name, corpus_spec="*", expected=None):
        items = [d for d in self.gen_corpus_schema_items(corpus_name, corpus_spec)]
        if expected is not None:
            self.failUnlessEqual(len(items), expected)
        self.doc_model.create_schema_items(items)
        self.ensure_pipeline_complete()

    def check_groupings(self, ex_tag, ex_grouping_key):
        # open all grouping-tag schemas - should be only 1
        key = ["schema_id", "rd.msg.grouping-tag"]
        result = self.doc_model.open_view(key=key, reduce=False,
                                          include_docs=True)
        # Check that grouping-tag specifies a tag for us
        rows = result['rows']
        self.failUnlessEqual(len(rows), 1)
        self.failUnlessEqual(rows[0]['doc']['tag'], ex_tag)
        key = ["schema_id", "rd.grouping.summary"]
        result = self.doc_model.open_view(key=key, reduce=False,
                                          include_docs=True)
        rows = result['rows']
        self.failUnlessEqual(len(rows), 1, pformat(rows))
        self.failUnlessEqual(rows[0]['doc']['rd_key'], ex_grouping_key)


    def test_simple_notification(self):
        ndocs = self.load_corpus("hand-rolled", "sent-email-simple-reply")
        self.ensure_pipeline_complete()
        ex_tag = 'identity-email-raindrop_test_user@mozillamessaging.com'
        # The back-end boostrap process has arranged for "our identities" to
        # be associated with the inflow grouping.
        ex_grouping_key = ['display-group', 'inflow']
        self.check_groupings(ex_tag, ex_grouping_key)

    def test_bulk_sender(self):
        # first run the extension.
        self.test_simple_notification()

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
        self.doc_model.create_schema_items([si])
        self.ensure_pipeline_complete()

        ex_tag = 'identity-email-raindrop_test_recip@mozillamessaging.com'
        # We expect a grouping-summary for this sender (ie, it is no
        # longer in the 'inflow' group.)
        ex_grouping_key = ['identity', ['email', 'raindrop_test_recip@mozillamessaging.com']]
        self.check_groupings(ex_tag, ex_grouping_key)

    def test_groups_single(self):
        # Initialize the corpus & database.
        ndocs = self.load_corpus("hand-rolled", "sent-email-simple-reply")
        self.ensure_pipeline_complete()

        msgid = ['email', '78cb2eb5dbc74cdd9691dcfdb266d1b9@something']
        body_schema = self.doc_model.open_schemas([(msgid, 'rd.msg.body')])[0]
        # should be one 'rd.convo.summary' doc in the DB.
        key = ['schema_id', 'rd.conv.summary']
        result = self.doc_model.open_view(key=key, reduce=False,
                                          include_docs=True)
        rows = result['rows']
        self.failUnlessEqual(len(rows), 1, pformat(rows))
        self.failUnlessEqual(rows[0]['doc']['rd_schema_id'], 'rd.conv.summary')
        conv_id = rows[0]['doc']['rd_key']

        # should also be exactly 1 'grouping summary'
        key = ['schema_id', 'rd.grouping.summary']
        result = self.doc_model.open_view(key=key, reduce=False,
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
        # now mark the one message in the conversation as 'read' - the entire
        # convo should vanish from the grouping-summary.
        si = {
            'rd_key': msgid,
            'rd_schema_id': 'rd.msg.seen',
            'rd_ext_id': 'rd.testsuite',
            'items' : {
                'seen': 'true',
                'outgoing_state': 'sent',
            }
        }
        self.doc_model.create_schema_items([si])
        self.ensure_pipeline_complete()
        # check the grouping.
        key = ['schema_id', 'rd.grouping.summary']
        result = self.doc_model.open_view(key=key, reduce=False,
                                          include_docs=True)
        rows = result['rows']
        self.failUnlessEqual(len(rows), 1, pformat(rows))
        self.failUnlessEqual(rows[0]['doc']['rd_schema_id'], 'rd.grouping.summary')
        doc_sum = rows[0]['doc']
        expected_doc = {
            'unread' : [],
            'num_unread': 0,
        }
        self.failUnlessDocEqual(doc_sum, expected_doc)

    def test_simple_twitter(self):
        ndocs = self.load_corpus("hand-rolled", "rd-msg-tweet-raw-1")
        self.ensure_pipeline_complete()
        ex_tag = 'twitter-status-update'
        ex_grouping_key = ['display-group', 'twitter']
        self.check_groupings(ex_tag, ex_grouping_key)

    def test_simple_twitter_reply(self):
        ndocs = self.load_corpus("hand-rolled", "rd-msg-tweet-raw-reply")
        self.ensure_pipeline_complete()
        # A twitter reply should have a tag with our identity and appear in
        # the inflow.
        ex_tag = 'identity-twitter-raindrop_test_user'
        ex_grouping_key = ['display-group', 'inflow']
        self.check_groupings(ex_tag, ex_grouping_key)

    def test_simple_twitter_mention(self):
        ndocs = self.load_corpus("hand-rolled", "rd-msg-tweet-raw-mention")
        self.ensure_pipeline_complete()
        # A tweet with @my_username should have a tag with our identity and
        # appear in the inflow.
        ex_tag = 'identity-twitter-raindrop_test_user'
        ex_grouping_key = ['display-group', 'inflow']
        self.check_groupings(ex_tag, ex_grouping_key)

    def test_bugzilla(self):
        ndocs = self.load_corpus("hand-rolled", "bugzilla")
        self.failUnlessEqual(ndocs, 1) # failed to load any corpus docs???
        self.ensure_pipeline_complete()

        # load the rd.msg.grouping-tag document and compare the results.
        key = ["schema_id", "rd.msg.grouping-tag"]
        result = self.doc_model.open_view(key=key, reduce=False,
                                          include_docs=True)

        # Make sure we got one result with type twitter
        rows = result['rows']
        self.failUnlessEqual(len(rows), 1)
        self.failUnlessEqual(rows[0]['doc']['tag'], "bugzilla-message");

class TestCustom(TestCaseWithTestDB):
    msg_template = """\
Delivered-To: raindrop_test_user@mozillamessaging.com
From: %s
To: %s
Date: Sat, 21 Jul 2009 12:13:14 -0000
Message-Id: <1234@something>

Hello everyone
"""
    my_addy = 'raindrop_test_user@mozillamessaging.com'
    other_addy = 'someone@somewhere.com'
    bulk_addy = 'newsletter@somewhere.com'


    def make_config(self):
        config = TestCaseWithTestDB.make_config(self)
        # now clobber it with a fake imap account which has our test user.
        config.accounts.clear()
        acct = config.accounts['test'] = {}
        acct['proto'] = 'imap'
        acct['id'] = 'imap_test'
        acct['username'] = self.my_addy
        return config

    def check_grouping(self, from_addy, to_addys, expected_addy, bulk_flag):
        ex_tag = 'identity-email-' + expected_addy
        return self.check_grouping_raw(from_addy, to_addys, ex_tag, bulk_flag)

    def check_grouping_raw(self, from_addy, to_addys, expected_tag, bulk_flag):
        to_str = ",".join(to_addys)
        msg = self.msg_template % (from_addy, to_str)
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
        self.doc_model.create_schema_items([si])
        if bulk_flag:
            si = {
                'rd_key': ['identity', ['email', self.bulk_addy]],
                'rd_schema_id': 'rd.identity.sender-flags',
                'rd_ext_id': 'rd.testsuite',
                'items' : {
                    'bulk': 'true',
                }
            }
            self.doc_model.create_schema_items([si])
        self.ensure_pipeline_complete()
        # should also be exactly 1 'grouping-tag' schema for the message.
        rd_key = ['email', '1234@something']
        docs = self.doc_model.open_schemas([(rd_key, 'rd.msg.grouping-tag')])
        doc = docs[0]
        self.failUnless(doc, 'no grouping-tag schema')
        self.failUnlessEqual(doc['tag'], expected_tag)

    # This table from msg-email-to-grouping-tag
    #Scenario                       no bulk flag          bulk flag
    #-----------------------        --------              ----------

    #From: you; to: bulk            you/inflow            bulk 
    def test_you_bulk(self):
        return self.check_grouping(self.my_addy, [self.bulk_addy],
                                   self.my_addy, False)

    def test_you_bulk_flagged(self):
        return self.check_grouping(self.my_addy, [self.bulk_addy],
                                   self.bulk_addy, True)
    
    #From: you; to: other           you/inflow            you/inflow
    def test_you_other(self):
        return self.check_grouping(self.my_addy, [self.other_addy],
                                   self.my_addy, False)

    def test_you_other_flagged(self):
        return self.check_grouping(self.my_addy, [self.other_addy],
                                   self.my_addy, True)

    #From: other; to: bulk          bulk* or other        bulk
    def test_other_bulk(self):
        return self.check_grouping(self.other_addy, [self.bulk_addy],
                                   self.bulk_addy, False)

    def test_other_bulk_flagged(self):
        return self.check_grouping(self.other_addy, [self.bulk_addy],
                                   self.bulk_addy, True)

    #From: other; to: you           you/inflow            you/inflow
    def test_other_you(self):
        return self.check_grouping(self.other_addy, [self.my_addy],
                                   self.my_addy, False)

    def test_other_you_flagged(self):
        return self.check_grouping(self.other_addy, [self.my_addy],
                                   self.my_addy, True)

    #From: other; to: bulk, you     you/inflow            you/inflow
    def test_other_bulk_you(self):
        return self.check_grouping(self.other_addy,
                                   [self.my_addy, self.bulk_addy],
                                   self.my_addy, False)

    def test_other_bulk_you_flagged(self):
        return self.check_grouping(self.other_addy,
                                   [self.my_addy, self.bulk_addy],
                                   self.my_addy, True)

    #From: bulk ; to: other         bulk or *other         bulk 
    def test_bulk_other(self):
        return self.check_grouping(self.bulk_addy, [self.other_addy],
                                   self.other_addy, False)

    def test_bulk_other_flagged(self):
        return self.check_grouping(self.bulk_addy, [self.other_addy],
                                   self.bulk_addy, True)

    #From: bulk ; to: you           you                   bulk 
    def test_bulk_you(self):
        return self.check_grouping(self.bulk_addy, [self.my_addy],
                                   self.my_addy, False)

    def test_bulk_you_flagged(self):
        return self.check_grouping(self.bulk_addy, [self.my_addy],
                                   self.bulk_addy, True)

    #From: bulk ; to: other, you    you/inflow            bulk
    def test_bulk_other_you(self):
        return self.check_grouping(self.bulk_addy,
                                   [self.other_addy, self.my_addy],
                                   self.my_addy, False)

    def test_bulk_other_you_flagged(self):
        return self.check_grouping(self.bulk_addy,
                                   [self.other_addy, self.my_addy],
                                   self.bulk_addy, True)

    #From: other; to: <none>        other                 other
    def test_other_none(self):
        return self.check_grouping(self.other_addy, [], self.other_addy, False)

    def test_other_none_flagged(self):
        return self.check_grouping(self.other_addy, [], self.other_addy, True)

    #From: bulk ; to: <none>        bulk                  bulk
    def test_bulk_none(self):
        return self.check_grouping(self.bulk_addy, [], self.bulk_addy, False)

    def test_bulk_none_flagged(self):
        return self.check_grouping(self.bulk_addy, [], self.bulk_addy, True)

    def test_folder(self):
        si = {'rd_key': ['email', '1234@something'],
              'rd_schema_id': 'rd.msg.imap-locations',
              'rd_source' : None,
              'rd_ext_id': 'rd.testsuite',
              'items': {
                'locations': [
                    {'folder_name': 'parent/child',
                     'folder_delim': '/',
                     'account': 'testsuite-account',
                    }
                ]
              },
            }
        self.doc_model.create_schema_items([si])
        self.check_grouping_raw(self.bulk_addy, [], "folder-parent/child", True)

    def test_folder_none(self):
        # this time the item is not in any imap folders.
        si = {'rd_key': ['email', '1234@something'],
              'rd_schema_id': 'rd.msg.imap-locations',
              'rd_source' : None,
              'rd_ext_id': 'rd.testsuite',
              'items': {
                'locations': [],
              },
            }
        self.doc_model.create_schema_items([si])
        self.check_grouping_raw(self.bulk_addy, [], "archived", False)

class TestGroupingSummaries(TestCaseWithTestDB):
    msg_template = """\
Delivered-To: raindrop_test_user@mozillamessaging.com
From: someone@somewhere
To: %s
Date: Sat, 21 Jul 2009 12:13:14 -0000
Message-Id: <%s>

Hello everyone
"""
    def test_multiple_tags(self):
        items = []
        grouping_key = ['grouping', 'whateva']
        # first create a grouping with 2 tags
        tag_user_1 = "identity-email-user1@something"
        tag_user_2 = "identity-email-user2@something"
        si = {'rd_key': grouping_key,
              'rd_schema_id': 'rd.grouping.info',
              'rd_source' : None,
              'rd_ext_id': 'rd.testsuite',
              'items': {'grouping_tags': [tag_user_1, tag_user_2]},
              }
        items.append(si)

        for addy, msgid in [('user1@something', '1234@something'),
                            ('user2@something', '5678@something',)
                           ]:
            msg = self.msg_template % (addy, msgid)
            si = {'rd_key': ['email', msgid],
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
            items.append(si)
        self.doc_model.create_schema_items(items)
        self.ensure_pipeline_complete()
        docs = self.doc_model.open_schemas([(grouping_key, 'rd.grouping.summary')])
        self.failUnlessEqual(len(docs), 1)
        doc = docs[0]
        self.failUnlessEqual(doc['rd_key'], grouping_key)
        # both messages should show in the summary.
        self.failUnlessEqual(doc['num_unread'], 2)
