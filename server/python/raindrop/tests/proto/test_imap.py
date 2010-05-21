from __future__ import with_statement
import sys
import types
import threading
import re
import errno
import socket
import SocketServer
import imaplib
import email
import rfc822
import time
from pprint import pformat

from raindrop.model import get_doc_model
import raindrop.proto.imap

from raindrop.tests import TestCaseWithTestDB, FakeOptions
from raindrop.proc.base import Rat

from imapclient.response_parser import parse_response
from imapclient.imap_utf7 import encode as encode_imap_utf7
from imapclient.imap_utf7 import decode as decode_imap_utf7

import logging
logger = logging.getLogger(__name__)

IMAP_SERVER_HOST='127.0.0.1'
IMAP_SERVER_PORT=6579

# helpers lifted from twisted.
def parseAddr(addr):
    if addr is None:
        return [(None, None, None),]
    addrs = email.Utils.getaddresses([addr])
    return [[fn or None, None] + addr.split('@') for fn, addr in addrs]

def getEnvelope(headers):
    date = headers.get('date')
    subject = headers.get('subject')
    from_ = headers.get('from')
    sender = headers.get('sender', from_)
    reply_to = headers.get('reply-to', from_)
    to = headers.get('to')
    cc = headers.get('cc')
    bcc = headers.get('bcc')
    in_reply_to = headers.get('in-reply-to')
    mid = headers.get('message-id')
    return (date, subject, parseAddr(from_), parseAddr(sender),
        reply_to and parseAddr(reply_to), to and parseAddr(to),
        cc and parseAddr(cc), bcc and parseAddr(bcc), in_reply_to, mid)

def _quote(s):
    return '"%s"' % (s.replace('\\', '\\\\').replace('"', '\\"'),)

def _literal(s):
    return '{%d}\r\n%s' % (len(s), s)

NAMESPACE_DELIM = "/"

def _needsLiteral(s):
    # Change this to "return 1" to wig out stupid clients
    return '\n' in s or '\r' in s or len(s) > 1000

def collapseNestedLists(items):
    pieces = []
    for i in items:
        if i is None:
            pieces.extend([' ', 'NIL'])
        elif isinstance(i, (int, long)):
            pieces.extend([' ', str(i)])
        elif isinstance(i, types.StringTypes):
            if _needsLiteral(i):
                pieces.extend([' ', '{', str(len(i)), '}', NAMESPACE_DELIM, i])
            else:
                pieces.extend([' ', _quote(i)])
        elif hasattr(i, 'read'):
            d = i.read()
            pieces.extend([' ', '{', str(len(d)), '}', NAMESPACE_DELIM, d])
        else:
            pieces.extend([' ', '(%s)' % (collapseNestedLists(i),)])
    return ''.join(pieces[1:])

class IMAPMessage:
    def __init__(self, uid, flags, msg_src):
        self.uid = uid
        self.flags = flags
        self.body = msg_src
        self.headers = email.message_from_string(msg_src)

    def get_internal_date(self):
        return self.headers['date']
        
class IMAPMailbox:
    def __init__(self, name, delim, flags=None, messages=None):
        self.name = name
        self.delim = delim
        self.flags = flags or []
        self.messages = messages or []

    def get_message_count(self):
        return len(self.messages)

    def get_recent_count(self):
        return len(self.messages)//2

    def get_uid_validity(self):
        return 1

    def add_flags(self, msg, flags):
        for flag in flags:
            if flag=='\\Deleted':
                self.messages.remove(msg)
                return
            else:
                if flag not in msg.flags:
                    msg.flags.append(flag)

class IMAPServer:
    _username = None
    _password = None
    def __init__(self):
        self.mailboxes = []

    def get_ident(self):
        return "Test IMAP Server"

    def list_capabilities(self):
        return ['IMAP4rev1']

    def login(self, username, password):
        return username == self._username and password == self._password

    def add_mailbox(self, mailbox):
        self.mailboxes.append(mailbox)

class IMAPSocketServer(SocketServer.ThreadingTCPServer):
    def __init__(self, testcase, listening_event, *args, **kw):
        self.listening_event = listening_event
        self.testcase = testcase
        SocketServer.ThreadingTCPServer.__init__(self, *args, **kw)

    def server_activate(self):
        SocketServer.ThreadingTCPServer.server_activate(self)
        self.listening_event.set()

    def finish_request(self, request, client_address):
        self.RequestHandlerClass(request, client_address, self, self.testcase.imap_server)


class IMAPHandler(SocketServer.StreamRequestHandler):
    current_mbox = None
    login_lock = threading.Lock() # shared amongst all instances
    def __init__(self, request, client_address, server, imap):
        self.imap = imap
        self._queued_async = []
        SocketServer.StreamRequestHandler.__init__(self, request, client_address, server)

    def send_bad_response(self, tag = None, message = ''):
        self._respond('BAD', tag, message)

    def send_positive_response(self, tag = None, message = ''):
        self._respond('OK', tag, message)

    def send_negative_response(self, tag = None, message = ''):
        self._respond('NO', tag, message)

    def send_untagged_response(self, message):
        self._respond(message, None, None)
        
    def _respond(self, state, tag, message):
        if state in ('OK', 'NO', 'BAD') and self._queued_async:
            lines = self._queuedAsync
            self._queuedAsync = []
            for msg in lines:
                self._respond(msg, None, None)
        if not tag:
            tag = '*'
        if message:
            self.send_line(' '.join((tag, state, message)))
        else:
            self.send_line(' '.join((tag, state)))

    def send_line(self, line):
        self.wfile.write(line + "\r\n")

    def handle(self):
        imap = self.imap
        msg = '[CAPABILITY %s] %s Ready' % (' '.join(imap.list_capabilities()), imap.get_ident())
        self.send_positive_response(message=msg)

        while True:
            line = self.rfile.readline()
            #sys.stdout.write("GOT request %r\n" % (line,))
            if not line:
                break # socket closed.
            if getattr(self.server.testcase, 'is_timeout_test', False):
                continue # no response - client should timeout

            look = line.split(None, 1)[0]
            if look=="UID":
                uid = True
                args = line.split(None, 3)[1:]
            else:
                uid = False
                args = line.split(None, 2)
            rest = None
            if len(args) == 3:
                tag, cmd, rest = args
            elif len(args) == 2:
                tag, cmd = args
            elif len(args) == 1:
                tag = args[0]
                self.send_bad_response(tag, 'Missing command')
                continue
            else:
                self.send_bad_response(None, 'Null command')
                continue
            uid = False
            if cmd == "UID":
                if not rest:
                    self.send_bad_response(tag, 'Missing command after UID')
                    continue
                cmd, rest = rest.split(None, 1)
                uid = True

            handler = getattr(self, 'handle_' + cmd.lower(), None)
            if handler is None:
                self.send_bad_response(tag, 'unknown command %r' % cmd)
                continue
            try:
                if handler(tag, rest, uid):
                    # handler wants to close the connection...
                    break
            except Exception, exc:
                logger.exception("test server failed")
                self.send_bad_response(message="Server Failed: %s" % exc)
                break

    def handle_capability(self, tag, rest, uid):
        self.send_untagged_response('CAPABILITY ' + ' '.join(self.imap.list_capabilities()))
        self.send_positive_response(tag, 'CAPABILITY completed')

    def handle_login(self, tag, rest, uid):
        # use a lock to avoid races between the threads
        with self.login_lock:
            if self.server.testcase.num_current_logins >= self.server.testcase.max_logins:
                self.server.testcase.num_failed_logins += 1
                self.send_negative_response(tag, "too many concurrent connections")
                return
            if self.server.testcase.num_transient_auth_errors:
                self.server.testcase.num_transient_auth_errors -= 1
                self.server.testcase.num_failed_logins += 1
                self.send_negative_response(tag, "transient auth failure...")
                return
    
            username, password = parse_response([rest])
            if self.imap.login(username, password):
                self.server.testcase.num_current_logins += 1
                self.send_positive_response(tag, 'LOGIN completed')
            else:
                self.send_negative_response(tag, 'LOGIN failed')

        if getattr(self.server.testcase, 'is_disconnect_after_login_test', False):
            return True

    def handle_logout(self, tag, rest, uid=False):
        self.send_untagged_response("BYE talk to you later")
        self.send_positive_response(tag, 'LOGOUT completed')
        self.server.testcase.num_current_logins -= 1
        return True

    def handle_list(self, tag, rest, uid):
        # If we are testing 'early premature' conection dropping, then
        # indicate the server should close before sending anything
        if getattr(self.server.testcase, 'is_disconnect_early_test', False):
            return True
        if self.server.testcase.num_transient_list_errors:
            self.server.testcase.num_transient_list_errors -= 1
            self.send_negative_response(tag, "something transient")
            return
        
        directory, pattern = parse_response([rest])
        assert directory == '', repr(directory)
        assert pattern == '*', repr(pattern)
        for mbox in self.imap.mailboxes:
            resp = ( mbox.flags, mbox.delim, encode_imap_utf7(mbox.name))
            self.send_untagged_response("LIST " + collapseNestedLists(resp))

        if getattr(self.server.testcase, 'is_disconnect_after_list_test', False):
            # disconnect *before* sending the OK response
            return True

        self.send_positive_response(tag, 'LIST completed')

    def handle_select(self, tag, rest, uid):
        return self._do_handle_select("SELECT", tag, rest, uid)

    def handle_examine(self, tag, rest, uid):
        return self._do_handle_select("EXAMINE", tag, rest, uid)

    def _do_handle_select(self, cmdname, tag, rest, uid):
        name = decode_imap_utf7(parse_response([rest])[0])
        self.current_mbox = None
        for mbox in self.imap.mailboxes:
            if name == mbox.name:
                self.current_mbox = mbox
                self.send_untagged_response(str(mbox.get_message_count()) + ' EXISTS')
                self.send_untagged_response(str(mbox.get_recent_count()) + ' RECENT')
                self.send_untagged_response('FLAGS (%s)' % ' '.join(mbox.flags))
                self.send_positive_response(None, '[UIDVALIDITY %d]' % mbox.get_uid_validity())
                self.send_positive_response(tag, '%s worked' % cmdname)
                break
        else:
            self.send_negative_response(tag, 'no such mailbox %r' % name)

    def _get_matching_messages(self, spec, uid):
        if isinstance(spec, int):
            # just an int was specified
            items = [spec]
        else:
            # a comma-sep'd list of messages - each may be a simple int, or
            # an int:int range.
            items = spec.split(",")
        for (seq, msg) in enumerate(self.current_mbox.messages):
            for item in items:
                if not isinstance(item, int) and ':' in item:
                    first, second = item.split(":")
                    first = 1 if first=="*" else int(first)
                    second = 1000000 if second=="*" else int(second)
                else:
                    first = second = item
                check = msg.uid if uid else seq
                if check >= first and check <= second:
                    # yay - matches.
                    yield seq, msg

    def handle_fetch(self, tag, rest, uid):
        spec, flags = parse_response([rest])
        for seq, msg in self._get_matching_messages(spec, uid):
            self._spew_message(seq, msg, flags, uid)
        self.send_positive_response(tag, "FETCH worked")

    def _spew_message(self, id, msg, flags, uid):
        bits = []
        if uid:
            bits.append('UID %s' % msg.uid)
        for flag in flags:
            if flag == 'FLAGS':
                bits.append('FLAGS (%s)' % ' '.join(msg.flags))
            elif flag == 'INTERNALDATE':
                idate = msg.get_internal_date()
                ttup = rfc822.parsedate_tz(idate)
                odate = time.strftime("%d-%b-%Y %H:%M:%S ", ttup[:9])
                if ttup[9] is None:
                    odate = odate + "+0000"
                else:
                    if ttup[9] >= 0:
                        sign = "+"
                    else:
                        sign = "-"
                    odate = odate + sign + str(((abs(ttup[9]) / 3600) * 100 + (abs(ttup[9]) % 3600) / 60)).zfill(4)
                bits.append('INTERNALDATE ' + _quote(odate))
            elif flag == 'RFC822.SIZE':
                bits.append('RFC822.SIZE %d' % len(msg.body))
            elif flag == 'ENVELOPE':
                bits.append('ENVELOPE ' + collapseNestedLists([getEnvelope(msg.headers)]))
            elif flag == 'BODY.PEEK[]':
                bits.append('BODY[] ' + _literal(msg.body))
            else:
                raise ValueError("Unsupported flag '%s'" % flag)
        self.send_untagged_response("%d FETCH (%s)" % (id, " ".join(bits)))

    def handle_search(self, tag, rest, uid):
        # todo: return something :)
        self.send_untagged_response("SEARCH 2")
        self.send_positive_response(tag, "SEARCH completed")

    def handle_store(self, tag, rest, uid):
        # XXX - no idea if these responses are correct - but our imap client
        # doesn't actually use the return codes so it doesn't really matter...
        spec, sub, params = parse_response([rest])
        if sub=="+FLAGS":
            for seq, msg in self._get_matching_messages(spec, uid):
                self.current_mbox.add_flags(msg, params)
                self.send_untagged_response("%d FETCH (FLAGS (%s))" % (msg.uid, " ".join(params)))
            self.send_positive_response(tag, "STORE added flags")
        else:
            raise ValueError("Unsupported store type '%s'" % (sub,))


test_message_src = """\
From: someone@somewhere
To: someone@somewhere
Date: Wed, 6 Jan 2010 19:33:19 -0500
Message-ID: <1234@somewhere>

Hello there
"""

class IMAP4TestBase(TestCaseWithTestDB):
    serverCTX = None
    mailboxes = []
    num_transient_auth_errors = 0
    num_transient_list_errors = 0
    num_fetch_requests = 0
    num_failed_logins = 0
    num_current_logins = 0
    max_logins = 99

    def setUp(self):
        self.old_backoff = raindrop.proto.imap.IMAPAccount.def_retry_backoff
        raindrop.proto.imap.IMAPAccount.def_retry_backoff = 1
        self.old_retries = raindrop.proto.imap.IMAPAccount.def_retry_count
        raindrop.proto.imap.IMAPAccount.def_retry_count = 1
        self.old_timeout = raindrop.proto.imap.IMAPAccount.def_timeout_response
        raindrop.proto.imap.IMAPAccount.def_timeout_response = 0.25

        self.imap_server = IMAPServer()
        self.imap_server._username = 'test_raindrop@test.mozillamessaging.com'
        self.imap_server._password = 'topsecret'

        listening_event = threading.Event()
        self._listenServer(listening_event)
        listening_event.wait()

        for mb in self.mailboxes:
            messages = [IMAPMessage(2, ['\Seen'], test_message_src)]
            self.imap_server.add_mailbox(IMAPMailbox(mb, "/", [], messages))

        super(IMAP4TestBase, self).setUp()
        def filter_log(record):
            # Almost all tests here cause the following messages...
            if record.msg.startswith("This IMAP server doesn't"):
                return True
            if record.msg.lower().startswith("failed to process"):
                return True

        self.log_handler.ok_filters.append(filter_log)

    def tearDown(self):
        raindrop.proto.imap.IMAPAccount.def_retry_backoff = self.old_backoff
        raindrop.proto.imap.IMAPAccount.def_retry_count = self.old_retries
        raindrop.proto.imap.IMAPAccount.def_timeout_response = self.old_timeout

        if self.server is not None:
            self.stop_test_server()

        super(IMAP4TestBase, self).tearDown()

    def _listenServer(self, listening_event):
        self.server = IMAPSocketServer(self,
                                       listening_event,
                                       (IMAP_SERVER_HOST, IMAP_SERVER_PORT),
                                       IMAPHandler)
        self.server_thread = threading.Thread(target=self.server.serve_forever)
        self.server_thread.start()

    def stop_test_server(self):
        self.server.shutdown()
        self.server_thread.join(5)
        if self.server_thread.isAlive():
            self.fail("test server didn't stop")
        self.server.server_close()
        self.server = None
        
    def make_config(self):
        config = TestCaseWithTestDB.make_config(self)
        # now clobber it with our imap account
        config.accounts.clear()
        acct = config.accounts['test'] = {}
        acct['proto'] = 'imap'
        acct['username'] = self.imap_server._username
        acct['password'] = self.imap_server._password
        acct['id'] = 'imap_test'
        acct['host'] = IMAP_SERVER_HOST
        acct['port'] = IMAP_SERVER_PORT
        acct['ssl'] = False
        return config

class TestSimpleFailures(IMAP4TestBase):
    def test_no_connect(self):
        def filter_log(record):
            ei = record.exc_info
            if ei and isinstance(ei[1], socket.error) and ei[1].args[0]==errno.ECONNREFUSED:
                return True
        self.log_handler.ok_filters.append(filter_log)

        # stop the server first.
        self.stop_test_server()
        # now attempt to connect to it.
        cond = self.get_conductor()
        cond.sync(self.pipeline.options, wait=True)
        status = cond.get_status_ob()['accounts']['imap_test']['status']
        self.failUnlessEqual(status['state'], Rat.BAD)
        self.failUnlessEqual(status['why'], Rat.UNREACHABLE)

    def test_timeout(self):
        def filter_log(record):
            ei = record.exc_info
            if ei and isinstance(ei[1], socket.timeout):
                return True
        self.log_handler.ok_filters.append(filter_log)
        self.is_timeout_test = True
        cond = self.get_conductor()
        cond.sync(self.pipeline.options, wait=True)
        status = cond.get_status_ob()['accounts']['imap_test']['status']
        self.failUnlessEqual(status['state'], Rat.BAD)
        self.failUnlessEqual(status['why'], Rat.TIMEOUT)


class TestDisconnectFailures(IMAP4TestBase):
    def setUp(self):
        IMAP4TestBase.setUp(self)
        def filter_log(record):
            msg = record.getMessage()
            # timing issues while testing means we may see a socket error
            # which gets logged as 'unexpected exception', or imaplib
            # handling an error which results in 'unexpected IMAP error'
            return msg.startswith("unexpected IMAP error") or \
                   msg.startswith("unexpected exception")
        self.log_handler.ok_filters.append(filter_log)

    def test_disconnect_early(self):
        self.is_disconnect_early_test = True
        cond = self.get_conductor()
        cond.sync(self.pipeline.options, wait=True)
        status = cond.get_status_ob()['accounts']['imap_test']['status']
        self.failUnlessEqual(status['state'], Rat.BAD)
        # don't have a specific 'why' state for this, so don't bother
        # testing is - 'state'==bad is good enough...

    def test_disconnect_late(self):
        self.is_disconnect_after_login_test = True
        cond = self.get_conductor()
        cond.sync(self.pipeline.options, wait=True)
        status = cond.get_status_ob()['accounts']['imap_test']['status']
        self.failUnlessEqual(status['state'], Rat.BAD)
        # don't have a specific 'why' state for this, so don't bother
        # testing is - 'state'==bad is good enough...

    def test_disconnect_later(self):
        self.is_disconnect_after_list_test = True
        cond = self.get_conductor()
        cond.sync(self.pipeline.options, wait=True)
        status = cond.get_status_ob()['accounts']['imap_test']['status']
        self.failUnlessEqual(status['state'], Rat.BAD)


class TestAuthFailures(IMAP4TestBase):
    def make_config(self):
        config = IMAP4TestBase.make_config(self)
        config.accounts['test']['username'] = "notme@anywhere"
        return config

    def test_bad_auth(self):
        cond = self.get_conductor()
        cond.sync(self.pipeline.options, wait=True)
        status = cond.get_status_ob()['accounts']['imap_test']['status']
        self.failUnlessEqual(status['state'], Rat.BAD)
        self.failUnlessEqual(status['why'], Rat.PASSWORD)

class TestSimpleEmpty(IMAP4TestBase):
    def test_simple_nothing(self):
        cond = self.get_conductor()
        cond.sync(self.pipeline.options, wait=True)
        status = cond.get_status_ob()['accounts']['imap_test']['status']
        self.failUnlessEqual(status['state'], Rat.GOOD)
        self.failUnlessEqual(status['what'], Rat.EVERYTHING)

    def test_simple_nothing_recovers_early(self):
        self.num_transient_auth_errors = 1
        self.test_simple_nothing()
        self.failUnlessEqual(self.num_transient_auth_errors, 0)

    def test_simple_nothing_recovers_late(self):
        def filter_log(record):
            if 'something transient' in record.getMessage():
                return True
        self.log_handler.ok_filters.append(filter_log)
        
        self.num_transient_list_errors = 1
        self.test_simple_nothing()
        self.failUnlessEqual(self.num_transient_list_errors, 0)

class TestSimpleMailboxes(IMAP4TestBase):
    mailboxes = ["foo/bar", u"extended \xa9har"]
    def test_simple(self):
        cond = self.get_conductor()
        cond.sync(self.pipeline.options, wait=True)
        status = cond.get_status_ob()['accounts']['imap_test']['status']
        self.failUnlessEqual(status['state'], Rat.GOOD)
        self.failUnlessEqual(status['what'], Rat.EVERYTHING)

    def test_simple_limited_connections(self):
        # XXX - we fail if we try only 1.
        self.max_logins = 2
        cond = self.get_conductor()
        cond.sync(self.pipeline.options, wait=True)
        status = cond.get_status_ob()['accounts']['imap_test']['status']
        self.failUnlessEqual(status['state'], Rat.GOOD)
        self.failUnlessEqual(status['what'], Rat.EVERYTHING)
        # check the server did actually reject at least one request.
        self.failUnless(self.num_failed_logins > 0)

    def test_locations_fetched(self):
        cond = self.get_conductor()
        cond.sync(self.pipeline.options, wait=True)
        # the base class puts the same message in both our folders, so there
        # should be one location record.
        key = ["schema_id", "rd.msg.imap-locations"]
        result = self.doc_model.open_view(key=key, reduce=False,
                                          include_docs=True)
        rows = result['rows']
        self.failUnlessEqual(len(rows), 1, pformat(rows))
        locations = rows[0]['doc']['locations']
        self.failUnlessEqual(len(locations), 2, pformat(locations))
        folders = sorted(l['folder_name'] for l in locations)
        self.failUnlessEqual(folders, sorted(self.mailboxes),
                             pformat(locations))

    def test_locations_deleted_messages(self):
        cond = self.get_conductor()
        cond.sync(self.pipeline.options, wait=True)
        # now write a 'deleted' schema item; the pipeline should call our
        # IMAP server with the delete request.
        msgid = "1234@somewhere"
        si = {'rd_key': ['email', msgid],
              'rd_schema_id': 'rd.msg.deleted',
              'rd_source' : None,
              'rd_ext_id': 'rd.testsuite',
              'items': {'deleted': True,
                        'outgoing_state': 'outgoing',
                        },
              }
        self.doc_model.create_schema_items([si])
        self.ensure_pipeline_complete()
        # ask it to re-sync, so it sees the message is no longer there...
        cond.sync(self.pipeline.options, wait=True)
        # the 'locations' record for this message should then be empty as it
        # was removed from both folders.
        key = ["schema_id", "rd.msg.imap-locations"]
        result = self.doc_model.open_view(key=key, reduce=False,
                                          include_docs=True)
        rows = result['rows']
        self.failUnlessEqual(len(rows), 1, pformat(rows))
        locations = rows[0]['doc']['locations']
        self.failIf(locations, pformat(rows[0]['doc']))

    def test_locations_deleted_folder(self):
        cond = self.get_conductor()
        cond.sync(self.pipeline.options, wait=True)
        # now 'delete' one of the IMAP folders and make sure this gets picked
        # up
        del self.imap_server.mailboxes[0]
        cond.sync(self.pipeline.options, wait=True)
        # the 'locations' record for this message should have 1 location
        key = ["schema_id", "rd.msg.imap-locations"]
        result = self.doc_model.open_view(key=key, reduce=False,
                                          include_docs=True)
        rows = result['rows']
        self.failUnlessEqual(len(rows), 1, pformat(rows))
        locations = rows[0]['doc']['locations']
        self.failUnlessEqual(len(locations), 1, pformat(rows[0]['doc']))
