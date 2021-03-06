from raindrop.tests import TestCaseWithCorpus

class TestSimpleCorpus(TestCaseWithCorpus):
    def test_simple_email(self):
        ndocs = self.load_corpus("hand-rolled", "sent-email-simple")
        self.failUnlessEqual(ndocs, 1) # failed to load any corpus docs???
        self.ensure_pipeline_complete()

        # There should be exactly one 'rd.msg.email' mail in our DB - check that.
        key = ["schema_id", "rd.msg.email"]
        result = self.doc_model.open_view(key=key, reduce=False,
                                          include_docs=True)
        rows = result['rows']
        self.failUnlessEqual(len(rows), 1, rows)
        doc = rows[0]['doc']
        # check our headers
        headers = doc['headers']
        # every single entry should be a list of at least one.
        for name, val in headers.iteritems():
            self.failUnless(isinstance(val, list) and len(val)>0, (name, val))
        # and some specific values.
        self.failUnless(len(headers['x-raindrop-note'])==2, str(headers['x-raindrop-note']))
        self.failUnlessEqual(headers['date'][0], 'Sat, 21 Jul 2009 12:13:14 -0000')

    def test_simple_body(self):
        ndocs = self.load_corpus("hand-rolled", "sent-email-simple")
        self.failUnlessEqual(ndocs, 1) # failed to load any corpus docs???
        self.ensure_pipeline_complete()

        # There should be exactly one 'rd.msg.body' mail in our DB - check that
        key = ["schema_id", "rd.msg.body"]
        result = self.doc_model.open_view(key=key, reduce=False,
                                          include_docs=True)
        rows = result['rows']
        self.failUnlessEqual(len(rows), 1, rows)
        doc = rows[0]['doc']
        # 'from' is not a list.
        self.failUnlessEqual(doc['from'], ['email', 'raindrop_test_user@mozillamessaging.com'])
        self.failUnlessEqual(doc['from_display'], 'Raindrop Test User')
        # 'to' is a list, but our test email has only 1 value.
        self.failUnlessEqual(doc['to'], [['email', 'raindrop_test_recip@mozillamessaging.com']])
        self.failUnlessEqual(doc['to_display'], ['Raindrop Test Recipient'])
        # 2 CCs
        self.failUnlessEqual(sorted(doc['cc']),
                             sorted([['email', 'raindrop_test_recip2@mozillamessaging.com'],
                                     ['email', 'raindrop_test_recip3@mozillamessaging.com']]))
        self.failUnlessEqual(sorted(doc['cc_display']),
                             sorted(['Raindrop Test Recipient 2',
                                     'Raindrop Test Recipient 3']))

    def test_simple_recips(self):
        ndocs = self.load_corpus("hand-rolled", "sent-email-simple")
        self.failUnlessEqual(ndocs, 1) # failed to load any corpus docs???
        self.ensure_pipeline_complete()

        # All people we sent mail to should get an identity and contact
        # record.
        for addy in ['raindrop_test_recip@mozillamessaging.com',
                     'raindrop_test_recip2@mozillamessaging.com',
                     'raindrop_test_recip3@mozillamessaging.com']:
            rd_key = ['identity', ['email', addy]]
            sch_id = 'rd.identity.exists'
            key = ["key-schema_id", [rd_key, sch_id]]
            result = self.doc_model.open_view(key=key, reduce=False,
                                              include_docs=True)
            self.failUnlessEqual(len(result['rows']), 1, addy)
            # and the contact
            
            key = ["key-schema_id", [rd_key, "rd.identity.contacts"]]
            result = self.doc_model.open_view(key=key, reduce=False,
                                              include_docs=True)
            self.failUnlessEqual(len(result['rows']), 1, addy)

    # Test for ticket #66 fix.
    def test_simple_quoted(self):
        ndocs = self.load_corpus("hand-rolled", "quoted-simple")
        self.failUnlessEqual(ndocs, 1) # failed to load any corpus docs???
        self.ensure_pipeline_complete()

        # load the hyperlinks document and compare the results.
        key = ["schema_id", "rd.msg.body.quoted"]
        result = self.doc_model.open_view(key=key, reduce=False,
                                          include_docs=True)
        
        # Make sure we got one result.
        self.failUnlessEqual(len(result['rows']), 1)
        
        # Make sure the right hyperlinks were found
        doc = result['rows'][0]['doc']
        self.failUnlessEqual(2, len(doc['parts']))

    def test_quoted_hyperlinks(self):
        ndocs = self.load_corpus("hand-rolled", "quoted-hyperlinks")
        self.failUnlessEqual(ndocs, 1) # failed to load any corpus docs???
        self.ensure_pipeline_complete()

        # load the hyperlinks document and compare the results.
        key = ["schema_id", "rd.attach.link"]
        result = self.doc_model.open_view(key=key, reduce=False,
                                          include_docs=True)
        
        expected = sorted([
                               {'username': '',
                                'fragment': '',
                                'path': u'/2009/01/01/upcoming-events-new-york-london',
                                'query': '',
                                'password': '',
                                'port': '',
                                'url': u'http://www.example.com/2009/01/01/upcoming-events-new-york-london',
                                'hostname': u'www.example.com',
                                'params': '',
                                'domain': u'example.com',
                                'scheme': u'http'},
                               {'username': '',
                                'fragment': '',
                                'path': u'/user/1/subscriptions',
                                'query': '',
                                'password': '',
                                'port': '',
                                'url': u'http://www.example.com/user/1/subscriptions',
                                'hostname': u'www.example.com',
                                'params': '',
                                'domain': u'example.com',
                                'scheme': u'http'},
                               {'username': '',
                                'fragment': '',
                                'path': u'/wiki/Sport_(disambiguation)',
                                'query': '',
                                'password': '',
                                'port': '',
                                'url': u'http://en.wikipedia.org/wiki/Sport_(disambiguation)',
                                'hostname': u'en.wikipedia.org',
                                'params': '',
                                'domain': u'wikipedia.org',
                                'scheme': u'http'},
                               {'username': '',
                                'fragment': '',
                                'path': u'/HQFyP',
                                'query': '',
                                'password': '',
                                'port': '',
                                'url': u'http://bit.ly/HQFyP',
                                'hostname': u'bit.ly',
                                'params': '',
                                'domain': u'bit.ly',
                                'scheme': u'http'},
                               {'username': '',
                                'fragment': '',
                                'path': u'/should-be-stripped',
                                'query': '',
                                'password': '',
                                'port': '',
                                'url': u'http://www.brackets.com/should-be-stripped',
                                'hostname': u'www.brackets.com',
                                'params': '',
                                'domain': u'brackets.com',
                                'scheme': u'http'},
                               {'username': '',
                                'fragment': '',
                                'path': u'/something/0,123,133.html',
                                'query': '',
                                'password': '',
                                'port': '',
                                'url': u'http://example.com/something/0,123,133.html',
                                'hostname': u'example.com',
                                'params': '',
                                'domain': u'example.com',
                                'scheme': u'http'},
                               {'username': '',
                                'fragment': '',
                                'path': u'',
                                'query': '',
                                'password': '',
                                'port': '',
                                'url': u'http://mozilla.com',
                                'hostname': u'mozilla.com',
                                'params': '',
                                'domain': u'mozilla.com',
                                'scheme': u'http'},
                               {'username': '',
                                'fragment': '',
                                'path': u'/wiki/Sport_(magazine))',
                                'query': '',
                                'password': '',
                                'port': '',
                                'url': u'http://en.wikipedia.org/wiki/Sport_(magazine))',
                                'hostname': u'en.wikipedia.org',
                                'params': '',
                                'domain': u'wikipedia.org',
                                'scheme': u'http'},
                               {'username': '',
                                'fragment': '',
                                'path': u'/about/index.html',
                                'query': '',
                                'password': '',
                                'port': '',
                                'url': u'http://python.org/about/index.html',
                                'hostname': u'python.org',
                                'params': '',
                                'domain': u'python.org',
                                'scheme': u'http'}
                             ], cmp=lambda x,y: cmp(x['hostname'], y['hostname']))
        # Make sure we got the expected results.
        self.failUnlessEqual(len(result['rows']), len(expected))

        # Make sure the right hyperlinks were found
        docs = sorted([r['doc'] for r in result['rows']], cmp=lambda x,y: cmp(x['hostname'], y['hostname']))
        for got, ex in zip(docs, expected):
            self.failUnlessDocEqual(got, ex)

    def test_twitter_notification(self):
        ndocs = self.load_corpus("hand-rolled", "twitter-notification")
        self.failUnlessEqual(ndocs, 1) # failed to load any corpus docs???
        self.ensure_pipeline_complete()

        # load the rd.msg.grouping-tag document and compare the results.
        key = ["schema_id", "rd.msg.grouping-tag"]
        result = self.doc_model.open_view(key=key, reduce=False,
                                          include_docs=True)
        # Make sure we got one result with type twitter
        rows = result['rows']
        self.failUnlessEqual(len(rows), 1)
        self.failUnlessEqual(rows[0]['doc']['tag'], "twitter-notification");

    def test_facebook_notification(self):
        # Load all facebook docs, but only facebook-friend should generate
        # an rd.msg.notification schema.
        ndocs = self.load_corpus("hand-rolled", "facebook-*")
        self.failUnlessEqual(ndocs, 3) # failed to load any corpus docs???
        self.ensure_pipeline_complete()

        # load the rd.msg.grouping-tag documents and compare the results.
        key = ["schema_id", "rd.msg.grouping-tag"]
        result = self.doc_model.open_view(key=key, reduce=False,
                                          include_docs=True)

        # Each of the test messages get a different 'tag'
        rows = result['rows']
        self.failUnlessEqual(len(rows), 3)
        got_tags = sorted(row['doc']['tag'] for row in rows)
        expected = ['facebook-comment', 'facebook-message', 'facebook-notification']
        self.failUnlessEqual(got_tags, expected)
