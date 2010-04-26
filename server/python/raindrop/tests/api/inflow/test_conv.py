from pprint import pformat
import rfc822

from twisted.internet import defer
from raindrop.tests.api import APITestCase, APITestCaseWithCorpus

class TestConvoSimple(APITestCaseWithCorpus):
    # "my identity" in the context of these tests should give us
    # 'raindrop_test_user@mozillamessaging.com' - and we know he
    # participates in at least the following convos.
    def get_known_msgs_from_identities(self, iids=None):
        known_msgs = set()
        if iids is None or \
           ('email', 'raindrop_test_user@mozillamessaging.com') in iids:
            # sent-email-simple.rfc822.txt
            known_msgs.add(('email', 'd3d08a8a534c464881a95b75300e9011@something'))
        # a skype convo
        if iids is None or ('skype', 'raindrop_test_user') in iids:
            # Our test user also has a skype identity.
            known_msgs.add(('skype-msg', 'raindrop_test_user-1'))
        return known_msgs

    def get_known_msgs_to_identities(self, iids=None):
        known_msgs = set()
        if iids is None or \
           ('email', 'raindrop_test_user@mozillamessaging.com') in iids:
            # sent-email-simple-reply.rfc822.txt
            known_msgs.add(('email', '78cb2eb5dbc74cdd9691dcfdb266d1b9@something'))
        return known_msgs

    def get_known_msgs_not_from_identities(self):
        # some 'random' messages not associated with our test identities.
        return set([('email', '07316ced2329a69aa169f3b9c6467703@bitbucket.org')])

    @defer.inlineCallbacks
    def sanity_check_convo(self, convo):
        # all messages in a convo must have the same conversation ID.
        messages = convo['messages']
        keys = [['key-schema_id', [msg['id'], 'rd.msg.conversation']]
                for msg in messages]
        result = yield self.doc_model.open_view(keys=keys, reduce=False,
                                                include_docs=True)
        for row in result['rows']:
            exp = convo['id']
            got = row['doc']['conversation_id']
            self.failUnlessEqual(exp, got,
                                 "wanted %r - got %r: %s" % (exp, got, pformat(row)))

        # No message should appear twice.
        seen_keys = set([tuple(msg['id']) for msg in messages])
        self.failUnlessEqual(len(seen_keys), len(messages), str(seen_keys))

    @defer.inlineCallbacks
    def test_identities_mine(self, iids=None):
        known_msgs = self.get_known_msgs_to_identities(iids)
        known_msgs.update(self.get_known_msgs_from_identities(iids))
        result = yield self.call_api("inflow/conversations/identities", ids=iids)
        seen = set()
        for convo in result:
            _ = yield self.sanity_check_convo(convo)
            for msg in convo['messages']:
                seen.add(tuple(msg['id']))

        self.failUnlessEqual(seen.intersection(known_msgs), known_msgs)
        unknown_msgs = self.get_known_msgs_not_from_identities()
        self.failUnlessEqual(seen.intersection(unknown_msgs), set())

    def test_identities_specific(self):
        # check it works when our default user is explicitly specified.
        iids = [('email', 'raindrop_test_user@mozillamessaging.com')]
        return self.test_identities_mine(iids)

    @defer.inlineCallbacks
    def test_direct(self, endpoint="inflow/conversations/direct",
                    schemas=None, should_exist=True):
        known_msgs = self.get_known_msgs_to_identities()
        result = yield self.call_api(endpoint, schemas=schemas)
        self.failUnless(result, "no conversations came back!")
        seen = set()
        for convo in result:
            _ = yield self.sanity_check_convo(convo)
            # only the first 3 messages have the 'summary' schemas
            for msg in convo['messages'][:3]:
                seen.add(tuple(msg['id']))
                # check the 'rd_*' fields have been removed.
                for schid, schvals in msg['schemas'].iteritems():
                    self.failIf('rd_key' in schvals, schvals)

                # at the moment we *always* return the summary schemas; we
                # know rd.msg.body is one of these.
                self.failUnless('rd.msg.body' in msg['schemas'], pformat(msg['schemas']))
                if schemas is not None:
                    if schemas != ['*'] and should_exist:
                        for schema in schemas:
                            self.failUnless(schema in msg['schemas'],
                                            "no schema %s in:\n%s" % (schema, pformat(msg['schemas'])))
                    if schemas == ['*'] or 'rd.msg.body' in schemas:
                        # Here we test that the *full* body schema was returned,
                        # not just the summary one. The 'body' field is not in the
                        # summary, so check it was actually returned.
                        body = msg['schemas']['rd.msg.body']
                        self.failUnless('body' in body, pformat(body))

        self.failUnlessEqual(seen.intersection(known_msgs), known_msgs)
        unknown_msgs = self.get_known_msgs_not_from_identities()
        self.failUnlessEqual(seen.intersection(unknown_msgs), set())

    @defer.inlineCallbacks
    def test_personal(self):
        _ = yield self.test_direct("inflow/conversations/personal")

    @defer.inlineCallbacks
    def test_personal_star(self):
        _ = yield self.test_direct("inflow/conversations/personal", ['*'])

    @defer.inlineCallbacks
    def test_personal_specific_conv(self):
        _ = yield self.test_direct("inflow/conversations/personal",
                                   ['rd.msg.conversation'])

    @defer.inlineCallbacks
    def test_personal_specific_body(self):
        _ = yield self.test_direct("inflow/conversations/personal",
                                   ['rd.msg.body'])

    @defer.inlineCallbacks
    def test_personal_specific_bad_schema(self):
        _ = yield self.test_direct("inflow/conversations/personal",
                                   ['rd.this-doesnt-exist'],
                                   False)

    @defer.inlineCallbacks
    def test_twitter(self):
        result = yield self.call_api("inflow/conversations/in_groups",
                                     keys=[["display-group", "twitter"]])
        # confirm 2 conversations (the @reply in the corpus winds up in the
        # inflow.
        self.failUnlessEqual(2, len(result), pformat(result))

        # get the conversations and sanity check them.
        ex_ids = [['tweet', 6119612045], ['email', '4ac4f85d89769_1de3156943569ffc176015a@mx007.twitter.com.tmail']]
        seen_ids = []
        for convo in result:
            _ = yield self.sanity_check_convo(convo)

            # confirm only one message
            self.failUnlessEqual(1, len(convo['messages']), pformat(convo))

            msg = convo['messages'][0]
            # record the message ID
            seen_ids.append(msg['id'])

        self.failUnlessEqual(sorted(seen_ids), sorted(ex_ids))

    @defer.inlineCallbacks
    def test_twitter_inflow(self):
        # here we test that the 2 @reply tweets do indeed appear in the
        # inflow.
        result = yield self.call_api("inflow/conversations/in_groups",
                                     keys=[["display-group", "inflow"]])
        # confirm the 2 conversations exist
        look = []
        for conv in result:
            if conv['id'] in (['twitter', 11111], ['twitter', 22222]):
                look.append(conv)
        self.failUnlessEqual(2, len(look), pformat(look))
        for conv in look:
            _ = yield self.sanity_check_convo(conv)
            # confirm only one message
            self.failUnlessEqual(1, len(conv['messages']), pformat(conv))

    @defer.inlineCallbacks
    def test_with_messages(self):
        known_msgs = self.get_known_msgs_to_identities()
        result = yield self.call_api("inflow/conversations/with_messages",
                                     keys=list(known_msgs))
        # should be 1 convo
        self.failUnlessEqual(len(result), 1)
        _ = yield self.sanity_check_convo(result[0])
        seen=set()
        for msg in result[0]['messages']:
            seen.add(self.doc_model.hashable_key(msg['id']))
            # check the 'rd_*' fields have been removed.
            for schid, schvals in msg['schemas'].iteritems():
                self.failIf('rd_key' in schvals, schvals)
        self.failUnlessEqual(known_msgs.intersection(seen), known_msgs)

    @defer.inlineCallbacks
    def test_by_id(self):
        known_msgs = self.get_known_msgs_to_identities()
        # find the conv IDs
        keys = [['key-schema_id', [mid, 'rd.msg.conversation']]
                for mid in known_msgs]
        result = yield self.doc_model.open_view(keys=keys, reduce=False,
                                                include_docs=True)
        # should be 1 convo
        self.failUnlessEqual(len(result['rows']), len(keys))
        conv_id = None
        for row in result['rows']:
            if conv_id is None:
                conv_id = row['doc']['conversation_id']
            else:
                self.failUnlessEqual(conv_id, row['doc']['conversation_id'])

        result = yield self.call_api("inflow/conversations/by_id",
                                     key=conv_id)
        _ = yield self.sanity_check_convo(result)
        seen = set()
        for msg in result['messages']:
            seen.add(self.doc_model.hashable_key(msg['id']))
        self.failUnlessEqual(known_msgs.intersection(seen), known_msgs)


# Some tests which don't use a corpus but instead introduce test messages
# manually.
class TestConvoMessageLimits(APITestCase):
    msg_template = """\
Delivered-To: raindrop_test_user@mozillamessaging.com
From: Raindrop Test User <Raindrop_test_user@mozillamessaging.com>
To: Raindrop Test Recipient <Raindrop_test_recip@mozillamessaging.com>
Date: %(date)s
Message-Id: %(mid)s
References: %(refs)s

Hello
"""

    def get_message_schema_item(self, msgid, refs, date=None):
        args = {'mid': '<'+msgid+'>',
                'refs': ' '.join(['<'+ref+'>' for ref in refs]),
                'date': rfc822.formatdate(date),
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

    @defer.inlineCallbacks
    def make_test_convo(self):
        # create one convo with 10 messages.
        items = [self.get_message_schema_item("0@something.com", [])]
        for i in range(1, 10):
            items.append(self.get_message_schema_item("%d@something.com" % i,
                                                      ["0@something.com"]))
        _ = yield self.doc_model.create_schema_items(items)
        _ = yield self.ensure_pipeline_complete()
        # should be 1 convo.
        key = ['schema_id', 'rd.conv.summary']
        result = yield self.doc_model.open_view(key=key, reduce=False,
                                                include_docs=True)
        self.failUnlessEqual(len(result['rows']), 1)
        cid = result['rows'][0]['doc']['rd_key']
        defer.returnValue(cid)

    @defer.inlineCallbacks
    def test_message_limit(self, limit=2):
        conv_id = yield self.make_test_convo()
        result = yield self.call_api("inflow/conversations/by_id",
                                     key=conv_id, message_limit=limit)
        self.failUnlessEqual(len(result['messages']), limit)
        defer.returnValue(result)

    @defer.inlineCallbacks
    def test_message_limit_none(self):
        _ = yield self.test_message_limit(0)

    @defer.inlineCallbacks
    def test_message_limit_lots(self):
        _ = yield self.test_message_limit(10)

    @defer.inlineCallbacks
    def test_message_no_limit(self):
        conv_id = yield self.make_test_convo()
        result = yield self.call_api("inflow/conversations/by_id",
                                     key=conv_id)
        self.failUnlessEqual(len(result['messages']), 10)
        # We asked for more messages than are in the summary, so
        # we expect the first to have a body schema and the last to have
        # no schemas
        self.failUnless('rd.msg.body' in result['messages'][0]['schemas'],
                        pformat(result))
        self.failIf(result['messages'][-1]['schemas'], pformat(result))

    @defer.inlineCallbacks
    def test_message_limit_summary(self):
        result = yield self.test_message_limit(2)
        # this should have only used the summary docs - so there will
        # be a 'body' schema, but no 'body' field in that schema.
        schema = result['messages'][0]['schemas']['rd.msg.body']
        self.failIf('body' in schema, pformat(schema))

    @defer.inlineCallbacks
    def test_message_schemas_exist(self):
        conv_id = yield self.make_test_convo()
        result = yield self.call_api("inflow/conversations/by_id",
                                     key=conv_id, message_limit=2,
                                     schemas=["rd.msg.body"])
        self.failUnlessEqual(len(result['messages']), 2)
        self.failUnless('rd.msg.body' in result['messages'][0]['schemas'],
                        pformat(result))
        # we explicitly asked for the body schema - so the entire schema
        # should be there - including the 'body' field which is stripped from
        # summaries.
        schema = result['messages'][0]['schemas']['rd.msg.body']
        self.failUnless('body' in schema, pformat(schema))

    @defer.inlineCallbacks
    def test_message_schemas_bad(self):
        conv_id = yield self.make_test_convo()
        result = yield self.call_api("inflow/conversations/by_id",
                                     key=conv_id, message_limit=2,
                                     schemas=["rd.unknown.schema.name"])
        self.failUnlessEqual(len(result['messages']), 2)
