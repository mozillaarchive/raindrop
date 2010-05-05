from raindrop.model import get_doc_model
from raindrop.pipeline import Pipeline
from raindrop.tests import TestCaseWithTestDB, FakeOptions
import raindrop.proto.smtp
from raindrop import sync
from raindrop.proc.base import Rat

import SocketServer
import logging
import time
import threading
import smtplib
logger = logging.getLogger(__name__)

SMTP_SERVER_HOST='127.0.0.1'
SMTP_SERVER_PORT=6578

class TestSMTPServer(SocketServer.ThreadingTCPServer):
    def __init__(self, *args, **kw):
        SocketServer.ThreadingTCPServer.__init__(self, *args, **kw)
        # in a dict so test-cases can override defaults.
        self.responses = {
            "EHLO": "250 nice to meet you",
            "QUIT": "221 see ya around\r\n",
            "MAIL FROM:": "250 ok",
            "RCPT TO:":   "250 ok",
            "RSET": "250 ok",
            "DATA": "354 go for it",
            ".": "250 gotcha",
        }
        self.connection_made_resp = '220 hello'
        self.num_connections = 0


class SMTPHandler(SocketServer.StreamRequestHandler):

    def setup(self):
        self.receiving_data = False
        SocketServer.StreamRequestHandler.setup(self)

    def handle(self):
        self.server.num_connections += 1
        self.wfile.write(self.server.connection_made_resp + "\r\n")
        while True:
            line = self.rfile.readline().strip()
            if not line:
                continue
            # *sob* - regex foo failed me.
            for k, v in self.server.responses.iteritems():
                if line.upper().startswith(k):
                    if isinstance(v, Exception):
                        raise v
                    handled = True
                    self.wfile.write(v + "\r\n")
                    break
            else:
                handled = False
            if line.upper() == "QUIT":
                break
            elif line.upper() == "DATA":
                self.receiving_data = True
            elif self.receiving_data:
                if line == ".":
                    self.receiving_data = False
            else:
                if not handled:
                    raise RuntimeError("test server not expecting %r" % (line,))


class TestSMTPBase(TestCaseWithTestDB):
    def setUp(self):
        TestCaseWithTestDB.setUp(self)
        self.conductor = self.get_conductor()
        self._listenServer()
        self.old_backoffs = (raindrop.proto.smtp.SMTPAccount.def_retry_count,
                             raindrop.proto.smtp.SMTPAccount.def_retry_backoff,
                             raindrop.proto.smtp.SMTPAccount.def_retry_backoff_max,
                            )
        raindrop.proto.smtp.SMTPAccount.def_retry_count = 1
        raindrop.proto.smtp.SMTPAccount.def_retry_backoff = 0.01
        raindrop.proto.smtp.SMTPAccount.def_retry_backoff_max = 0.01

    def _listenServer(self):
        self.server = TestSMTPServer((SMTP_SERVER_HOST, SMTP_SERVER_PORT),
                                     SMTPHandler)
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.start()
        time.sleep(0.01) # lame!  Ensure server listening...

    def tearDown(self):
        self.server.shutdown()
        self.server_thread.join(5)
        if self.server_thread.isAlive():
            self.fail("test server didn't stop")
        self.server.server_close()
        (raindrop.proto.smtp.SMTPAccount.def_retry_count,
         raindrop.proto.smtp.SMTPAccount.def_retry_backoff,
         raindrop.proto.smtp.SMTPAccount.def_retry_backoff_max,
                            ) = self.old_backoffs

        return TestCaseWithTestDB.tearDown(self)

    
# Simple test case writes an outgoing smtp schema, and also re-uses that
# same document for the 'sent' state.  This avoids any 'pipeline' work.
class TestSMTPSimple(TestSMTPBase):
    def _prepare_test_doc(self):
        doc_model = get_doc_model()
        # abuse the schema API to write the outgoing smtp data and the
        # 'state' doc in one hit.
        body = 'subject: hello\r\n\r\nthe body'
        items = {'smtp_from' : 'sender@test.com',
                 'smtp_to': ['recip1@test.com', 'recip2@test2.com'],
                 # The 'state' bit...
                 'sent_state': None,
                 'outgoing_state': 'outgoing',
                }
        sis = [
                { 'rd_key': ['test', 'smtp_test'],
                   'rd_ext_id': 'testsuite',
                   'rd_schema_id': 'rd.some_src_schema',
                   'items': {'outgoing_state': 'outgoing'},
                },
                {'rd_key': ['test', 'smtp_test'],
                 'rd_ext_id': 'testsuite',
                 'rd_schema_id': 'rd.msg.outgoing.smtp',
                 'items': items,
                 'attachments': {'smtp_body': {'data': body}},
                },
              ]
        
        doc_model.create_schema_items(sis)
        dids = [doc_model.get_doc_id_for_schema_item(si) for si in sis]
        return doc_model.open_documents_by_id(dids)

    def _send_test_doc(self, src_doc, raw_doc):
        details = {'host': SMTP_SERVER_HOST, 'port': SMTP_SERVER_PORT,
                   'id': 'smtp_test'}
        self.acct = raindrop.proto.smtp.SMTPAccount(get_doc_model(), details)
        self.acct.startSend(self.conductor, src_doc, raw_doc)

    def test_simple(self):
        src_doc, out_doc = self._prepare_test_doc()
        self._send_test_doc(src_doc, out_doc)
        # now re-open the doc and check the state says 'sent'
        src_doc = get_doc_model().db.openDoc(src_doc['_id'])
        self.failUnlessEqual(src_doc['sent_state'], 'sent')
        self.failUnlessEqual(self.server.num_connections, 1) # must have connected to the test server.
        # check the protocol recorded the success
        status = self.acct.status
        self.failUnlessEqual(status.get('state'), Rat.GOOD, status)
        self.failUnlessEqual(status.get('what'), Rat.EVERYTHING, status)

    def test_simple_rejected(self):
        src_doc, out_doc = self._prepare_test_doc()
        def filter_log(rec):
            return "sook sook sook" in rec.msg
        self.log_handler.ok_filters.append(filter_log)
        self.server.responses["MAIL FROM:"] = "500 sook sook sook"

        self._send_test_doc(src_doc, out_doc)
        # now re-open the doc and check the state says 'error'
        src_doc = get_doc_model().db.openDoc(src_doc['_id'])
        self.failUnlessEqual(src_doc['sent_state'], 'error')

        # check the protocol recorded the error.
        status = self.acct.status
        self.failUnlessEqual(status.get('state'), Rat.BAD, status)
        self.failUnlessEqual(status.get('what'), Rat.SERVER, status)
        self.failUnless('sook' in status.get('message', ''), status)

    def test_simple_connection_failed(self):
        def filter_log(rec):
            return "Out of disk space; try later" in rec.msg
        self.log_handler.ok_filters.append(filter_log)
        self.server.connection_made_resp = "452 Out of disk space; try later"

        src_doc, out_doc = self._prepare_test_doc()
        self._send_test_doc(src_doc, out_doc)
        # now re-open the doc and check the state says 'error'
        src_doc = get_doc_model().db.openDoc(src_doc['_id'])
        self.failUnlessEqual(src_doc['sent_state'], 'error')

# creates a real 'outgoing' schema, then uses the conductor to do whatever
# it does...
class TestSMTPSend(TestSMTPBase):
    def setUp(self):
        TestSMTPBase.setUp(self)
        # init the conductor so it hooks itself up for sending.
        self.get_conductor()

    def _prepare_test_doc(self):
        doc_model = get_doc_model()
        # write a simple outgoing schema
        items = {'body' : 'hello there',
                 'from' : ['email', 'test1@test.com'],
                 'from_display': 'Sender Name',
                 'to' : [
                            ['email', 'test2@test.com'],
                            ['email', 'test3@test.com'],
                        ],
                 'to_display': ['recip 1', 'recip 2'],
                 'cc' : [
                            ['email', 'test4@test.com'],
                    
                        ],
                 'cc_display' : ['CC recip 1'],
                 'subject': "the subject",
                 # The 'state' bit...
                 'sent_state': None,
                 'outgoing_state': 'outgoing',
                }
        result = doc_model.create_schema_items([
                    {'rd_key': ['test', 'smtp_test'],
                     'rd_ext_id': 'testsuite',
                     'rd_schema_id': 'rd.msg.outgoing.simple',
                     'items': items,
                    }])
        src_doc = doc_model.db.openDoc(result[0]['id'])
        return src_doc

    def make_config(self):
        config = TestCaseWithTestDB.make_config(self)
        # now clobber it with out smtp account
        config.accounts.clear()
        acct = config.accounts['test'] = {}
        acct['proto'] = 'smtp'
        acct['username'] = 'test_raindrop@test.mozillamessaging.com'
        acct['id'] = 'smtp_test'
        acct['host'] = SMTP_SERVER_HOST
        acct['port'] = SMTP_SERVER_PORT
        acct['ssl'] = False
        return config

    def test_outgoing(self):
        src_doc = self._prepare_test_doc()
        self.ensure_pipeline_complete()
        self.failUnlessEqual(self.server.num_connections, 1)

    def test_outgoing_with_unrelated(self):
        src_doc = self._prepare_test_doc()
        # make another document with the same rd_key, but also an empty
        # source.
        items = {'foo' : 'bar',}
        result = self.doc_model.create_schema_items([
                    {'rd_key': ['test', 'smtp_test'],
                     'rd_ext_id': 'testsuite',
                     'rd_schema_id': 'rd.msg.something-unrelated',
                     'items': items,
                    }])

        self.ensure_pipeline_complete()
        self.failUnlessEqual(self.server.num_connections, 1)

    def test_outgoing_twice(self):
        doc_model = get_doc_model()
        src_doc = self._prepare_test_doc()
        nc = self.server.num_connections
        self.ensure_pipeline_complete()
        self.failUnlessEqual(nc+1, self.server.num_connections)
        nc = self.server.num_connections
        # sync again - better not make a connection this time!
        # XXX - this isn't testing what it should - it *should* ensure
        # the pipeline does see the message again, but the conductor refusing
        # to re-send it due to the 'outgoing_state'.
        self.ensure_pipeline_complete()
        self.failUnlessEqual(nc, self.server.num_connections)


