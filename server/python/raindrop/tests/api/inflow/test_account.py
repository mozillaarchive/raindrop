from __future__ import with_statement
import os
import ConfigParser
from pprint import pformat

from twisted.internet import defer
from raindrop.tests.api import APITestCase

class TestAccount(APITestCase):
    @defer.inlineCallbacks
    def setUp(self):
        _ = yield APITestCase.setUp(self)
        # these tests may change a .ini file - so we take care not to
        # crunch a *real* one!
        # This is the cfg file the api uses.
        self.cfg_file = None
        dbname = self.config.couches['local']['name']
        cfg_file = os.path.expanduser("~/." + dbname)
        self.failIf(os.path.exists(cfg_file),
                    "Can't run this test while %r exists" % (cfg_file,))
        self.cfg_file = cfg_file

    @defer.inlineCallbacks
    def tearDown(self):
        _ = yield APITestCase.tearDown(self)
        if self.cfg_file is not None and os.path.exists(self.cfg_file):
            os.remove(self.cfg_file)

    @defer.inlineCallbacks
    def test_list_empty(self):
        result = yield self.call_api("inflow/account/list")
        self.failUnlessEqual(result, [])

    @defer.inlineCallbacks
    def test_set_simple(self):
        acct = {"host": "mail.foo.com",
                "port": 1234,
                "password": "topsecret",
                "the_password_value": "topsecret",
                "secret_token": "topsecret",
        }
        result = yield self.call_api("inflow/account/set", "POST", acct,
                                     id="test")
        self.failUnlessEqual(result, "ok")
        # now read it back.
        result = yield self.call_api("inflow/account/list")
        self.failUnlessEqual(len(result), 1, pformat(result))
        info = result[0]
        self.failUnlessEqual(info['host'], acct['host'])
        self.failUnlessEqual(info['port'], acct['port'])
        self.failUnlessEqual(info['password'], True)
        self.failUnlessEqual(info['the_password_value'], True)
        self.failUnlessEqual(info['secret_token'], True)

    @defer.inlineCallbacks
    def test_set_multiple(self):
        _ = yield self.test_set_simple()
        acct = {"host": "other.com",
                "port": 5678,
                "password": "asecret",
        }
        result = yield self.call_api("inflow/account/set", "POST", acct,
                                     id="test2")
        self.failUnlessEqual(result, "ok")
        # now read them back.
        result = yield self.call_api("inflow/account/list")
        self.failUnlessEqual(len(result), 2, pformat(result))
        acct1, acct2 = sorted(result, key=lambda d: d['id'])
        self.failUnlessEqual(acct1['host'], 'mail.foo.com')
        self.failUnlessEqual(acct2['host'], acct['host'])

    @defer.inlineCallbacks
    def test_set_merge(self):
        # write an existing section to the cfg file.
        with open(self.cfg_file, "w") as f:
            f.write("[some_section]\nfoo=bar")
        acct = {"host": "mail.foo.com",
                "port": 1234,
                }
        result = yield self.call_api("inflow/account/set", "POST", acct,
                                     id="test")
        self.failUnlessEqual(result, "ok")

        with open(self.cfg_file) as f:
            content = f.read()
        # check the config file still has the existing section we wrote.
        parser = ConfigParser.SafeConfigParser()
        parser.read([self.cfg_file])
        self.failUnless(parser.has_section("some_section"), content)
        self.failUnless(parser.has_option("some_section", "foo"), content)
        self.failUnlessEqual(parser.get("some_section", "foo"), "bar", content)
        # and the account should have another section.
        self.failUnlessEqual(len(parser.sections()), 2, content)

    @defer.inlineCallbacks
    def test_set_reloads(self):
        acct = {"host": "mail.foo.com"}
        result = yield self.call_api("inflow/account/set", "POST", acct,
                                     id="test")
        self.failUnlessEqual(result, "ok")
        # now read it back - but directly from our local config object.  This
        # is to ensure that processes which are already running and have
        # loaded the config see the change and magically get the new value.
        # (The API reads the file on each 'list' request, so isn't suitable
        # for testing this specific case)
        got = self.config.accounts['test']
        self.failUnless('host' in got, got)
        self.failUnlessEqual(got['host'], 'mail.foo.com')
