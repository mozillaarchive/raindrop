# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Raindrop.
#
# The Initial Developer of the Original Code is
# Mozilla Messaging, Inc..
# Portions created by the Initial Developer are Copyright (C) 2010
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#

import httplib
import socket
import errno
import select
from cStringIO import StringIO
from raindrop import json

import logging

logger = logging.getLogger(__name__)


class ChangesIterFactory(object):
    """Creates multiple iterators based on a single _changes feed.

    Each call to make_iter returns a new iterator.  This iterator never
    "blocks" - once created the iterator will return as many rows as
    are available (up to the batch size) then terminate - however, the
    make_iter call itself *may* block if no changes are currently available.

    All this is done from a single _changes feed connection.
    """
    def __init__(self):
        self.stopping = False
        self.current_seq = None
        self.is_waiting = False
        self.connection = None
        self.include_deps = False

    def stop(self):
        self.stopping = True
        # make a connection to the control socket so our 'select' wakes up.
        addr = self.control_socket.getsockname()
        temp_sock = socket.socket()
        try:
            temp_sock.connect(addr)
        except socket.error, exc:
            pass
        logger.debug('closed %r', self.connection.sock)

    def initialize(self, doc_model, start_seq, include_deps=False):
        self.include_deps = include_deps
        self.doc_model = doc_model
        self.current_seq = start_seq or 0
        # it isn't *necessary* to establish the connection yet, but we do
        # so fatal errors connecting to _changes are reported early.
        self._make_connection()
        self._chunk_buf = StringIO()

        # now create another socket so we can shutdown when asked.
        self.control_socket = socket.socket()
        self.control_socket.bind(('127.0.0.1', 0))
        self.control_socket.listen(1)
        logger.debug('initialize complete')

    def _change_to_elt(self, change):
        if 'error' in change or 'deleted' in change:
            return None
        last_change = change['changes'][-1]
        return change['id'], last_change['rev'], None, change['seq']

    def _make_connection(self):
        db = self.doc_model.db
        # We abuse httplib to establish the connection and read the headers,
        # then we swtich to non-blocking and handle all reading manually.
        c = httplib.HTTPConnection(db.host, db.port)
        # sadly no option for 'never timeout'
        timeout = 100000000
        path = "/%s/_changes?feed=continuous&timeout=%d&since=%d" % \
                (db.dbName, timeout, self.current_seq)
        c.request("GET", path)
        self.connection = c
        self.response = c.getresponse()
        # ensure all headers are fetched.
        self.response.begin()
        # now we are ready for our funcky non-blocking read process.
        c.sock.setblocking(False)

    def _read_line(self):
        # this is complicated due to chunking and non-blocking sockets.
        # We can't use readline etc as it doesn't correctly buffer prior
        # input when a read throws the EWOULDBLOCK error.  So we need to
        # manage this manually.
        # Each chunk looks like: num_bytes\r\njson_str\r\n
        # We take pains to always read what is available in the buffer and
        # avoid iterating over the stream char by char...
        sock = self.connection.sock
        while True:
            # Do we have enough in our buffer for an entire chunk?
            cur = self._chunk_buf.getvalue()
            bits = cur.split("\r\n", 1)
            if len(bits)==2:
                # we do have the chunk size - do we have the chunk itself,
                # including the tail?
                nbytes = int(bits[0], 16)
                rest_nbytes = nbytes + 2 # the crlf chunk tail.
                data = bits[1]
                if len(data) >= rest_nbytes:
                    # yay - we have a complete chunk...
                    this_chunk = data[:nbytes]
                    self._chunk_buf.seek(0)
                    self._chunk_buf.truncate()
                    self._chunk_buf.write(data[rest_nbytes:])
                    return this_chunk
            # So we don't have enough buffered - perform a read then try again.
            self._chunk_buf.write(sock.recv(4096))

    def _get_next_change(self, blocking):
        while True:
            if self.connection is None:
                self._make_connection()
            try:
                line = self._read_line()
            except socket.error, exc:
                if exc.args[0] == errno.EWOULDBLOCK:
                    if not blocking:
                        return None
                    # blocking request - use select to work out when we are ready
                    self.is_waiting = True
                    logger.debug('selecting %r', self.connection.sock)
                    socks = [self.connection.sock, self.control_socket]
                    ready, _, _ = select.select(socks, [], [])
                    if self.stopping:
                        return None
                    # only our connection should be ready if not stopping.
                    assert ready == [self.connection.sock]
                    self.is_waiting = False
                    logger.debug('select ready')
                    continue
                # some other socket error - reestablish the connection.
                logger.error('_changed feed saw socket error: %s', exc)
                self.connection = None
                continue

            if not line:
                # ack - connection closed unexpectedly - try again...
                self.connection = None
                continue
            if not line.strip():
                # a 'heartbeat' line - just ignore it and read the next.
                continue
            # got a line - maybe it is the very last line due to the timeout?
            change = json.loads(line)
            if 'last_seq' in change:
                # it is the last line - must reconnect and start again.
                self.connection = None
                continue
            # it is good (in theory :)
            assert 'seq' in change, repr(line)
            return change

    def make_iter(self, batch_size):
        these_elts = []
        # try and read a line, blocking if none are available.
        change = self._get_next_change(True)
        if change is None:
            return

        self.current_seq = change['seq']
        elt = self._change_to_elt(change)
        if elt is not None:
            these_elts.append(elt)
            yield elt

        # now keep reading until no more are left.
        while not self.stopping and len(these_elts) < batch_size:
            change = self._get_next_change(False)
            if change is None:
                # out of changes!
                break
            self.current_seq = change['seq']
            elt = self._change_to_elt(change)
            if elt is not None:
                these_elts.append(elt)
                yield elt

        # no more _changes waiting or batch size hit.  Do deps.
        if self.include_deps:
            # find any documents which declare they depend on the documents
            # in the list, then lookup the "source" of that doc
            # (ie, the one that "normally" triggers that doc to re-run)
            # and return that source.
            all_ids = set()
            keys = []
            for elt in these_elts:
                src_id = elt[0]
                all_ids.add(src_id)
                try:
                    _, rd_key, schema_id = self.doc_model.split_doc_id(src_id)
                except ValueError:
                    # not a raindrop document - ignore it.
                    continue
                keys.append(["dep", [rd_key, schema_id]])
            if keys:
                results = self.doc_model.open_view(keys=keys, reduce=False)
                rows = results['rows']
                # Find all unique IDs.
                result_seq = set()
                for row in rows:
                    src_id = row['value']['rd_source'][0]
                    if src_id not in all_ids:
                        yield src_id, None, None, self.current_seq
