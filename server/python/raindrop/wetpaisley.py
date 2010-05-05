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
# Portions created by the Initial Developer are Copyright (C) 2009
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#

import sys
from urllib import urlencode, quote
import httplib
import base64
import socket
import errno
from collections import deque
import time

import logging
logger=logging.getLogger(__name__)

try:
    import simplejson as json
except ImportError:
    import json # Python 2.6

# from the couchdb package; not sure what makes these names special...
def _encode_options(options):
    retval = {}
    for name, value in options.items():
        if name in ('key', 'startkey', 'endkey', 'include_docs') \
                or not isinstance(value, basestring):
            value = json.dumps(value, allow_nan=False)
        retval[name] = value
    return retval

class CouchError(Exception):
    def __init__(self, status, reason, body):
        self.status = status
        self.reason = reason
        self.body = body
        Exception.__init__(self, status, reason, body)

class CouchNotFoundError(CouchError):
    pass

class CouchDB():
    _has_adbs = None # does this couch support the old _all_docs_by_seq api?
    Error = CouchError
    NotFoundError = CouchNotFoundError
    def __init__(self, host, port=5984, dbName=None, username=None, password=None):
        self.host = host
        self.port = port
        self.dbName = dbName
        self.username = username
        self.password = password
        self.connections_available = deque()

    def _check_error(self, response):
        status = int(response.status)
        if 200 <= status < 300:
            return
        # it is an error - some errors get their own class.
        if status == 404:
            exc_class = self.NotFoundError
        else:
            exc_class = self.Error
        raise exc_class(status, response.reason, response.read())
        
    def _request(self, method, uri, body = None, headers = None):
        return json.loads(self._rawrequest(method, uri, body, headers))

    def _rawrequest(self, method, uri, body = None, headers = None):
        if headers is None:
            headers = {}
        if 'Accept' not in headers:
            headers['Accept'] = 'application/json'

        new_con_retries = 3
        while True: # retry on exceptions using pooled connections
            try:
                conn = self.connections_available.popleft()
                reused = True
            except IndexError:
                conn = httplib.HTTPConnection(self.host, self.port)
                reused = False
            response = None
            try:
                try:
                    conn.request(method, uri, body, headers)
                    response = conn.getresponse()
                    self._check_error(response)
                    return response.read()
                except (httplib.BadStatusLine, socket.error), exc:
                    # couch may discard old connections resulting in these
                    # exceptions
                    if isinstance(exc, socket.error) and \
                       exc.errno not in [errno.ECONNRESET, errno.ECONNABORTED]:
                        logger.warn("non retryable error: %s", exc)
                        raise
                    conn.close()
                    conn = response = None
                    if not reused:
                        if new_con_retries <= 0:
                            logger.warn("ran out of retries on brand-new connection: %s", exc)
                            raise
                        logger.info("retryable error on brand-new connection")
                        new_con_retries -= 1
                        # we might be out of sockets or hit some other
                        # load-based error, so sleep a little...
                        time.sleep(2)
                        continue
                    logger.debug("re-connecting after error using pooled connection: %s",
                                exc)
    
            finally:
                if conn is None and response is None:
                    pass
                elif response is None:
                    conn.close()
                elif response.will_close or len(self.connections_available)>10:
                    # can't/won't reuse this connection.
                    conn.close()
                else:
                    # just incase someone hasn't read it yet.
                    response.read()
                    self.connections_available.append(conn)
                    logger.debug("reusing connection - now %d available",
                                 len(self.connections_available))

    def _getPage(self, uri, **kwargs):
        """
        C{getPage}-like.
        """
        if isinstance(uri, unicode): # XXX - is this the best place for this?
            uri = uri.encode("utf-8")
        url = self.url_template % (uri,)
        kwargs["headers"] = headers = {"Accept": "application/json"}
        if self.username:
            auth = base64.b64encode(self.username + ":" + self.password)
            headers["Authorization"] = "Basic " + auth
        _request('GET', uri, None, headers)

    def postob(self, uri, ob):
        body = json.dumps(ob, allow_nan=False)
        assert isinstance(body, str), body # must be ready to send on the wire
        return self.post(uri, body)

    def openView(self, docId, viewId, **kwargs):
        try:
            headers = {"Accept": "application/json"}
            uri = "/%s/_design/%s/_view/%s" % (self.dbName, docId, viewId)

            opts = kwargs.copy()
            if 'keys' in opts:
                method = 'POST'
                body_ob = {'keys': opts.pop('keys')}
                body = json.dumps(body_ob, allow_nan=False)
                assert isinstance(body, str), body
            else:
                method = 'GET'
                body = None
            args = _encode_options(opts)
            if args:
                uri += "?%s" % (urlencode(args),)

            return self._request(method, uri, body, headers)
        except:
            raise
            return {}

    def openDoc(self, docId, revision=None, full=False, attachment="",
                attachments=False):
        if attachment:
            uri = "/%s/%s/%s" % (self.dbName, docId, quote(attachment))
            return self._rawrequest('GET', uri)

        uri = "/%s/%s" % (self.dbName, docId)
        try:
            obj = self._request('GET', uri, None, None)
        except CouchNotFoundError:
            # XXX - what is the story here?  0.10 sure returns a 404, but
            # does anyone else return a 200 with 'error'?
            return {}
        if 'error' in obj and obj['error'] == 'not_found':
            return {}
        return obj

    def saveAttachment(self, docId, name, data,
                       content_type="application/octet-stream",
                       revision=None):
        """
        Save/create an attachment to a document in a given database.

        @param dbName: identifier of the database.
        @type dbName: C{str}

        @param docId: the identifier of the document.
        @type docId: C{str}

        #param name: name of the attachment
        @type name: C{str}

        @param body: content of the attachment.
        @type body: C{sequence}

        @param content_type: content type of the attachment
        @type body: C{str}

        @param revision: if specified, the revision of the attachment this
                         is updating
        @type revision: C{str}
        """
        # Responses: ???
        # 409 Conflict, 500 Internal Server Error
        url = "/%s/%s/%s" % (self.dbName, docId, name)
        if revision:
            url = url + '?rev=' + revision
        headers = {"Accept": "application/json",
                   "Content-Type": content_type,
                  }
        return self._request('PUT', url, data, headers)

    def updateDocuments(self, user_docs):
        # update/insert/delete multiple docs in a single request using
        # _bulk_docs
        # from couchdb-python.
        docs = []
        for doc in user_docs:
            if isinstance(doc, dict):
                docs.append(doc)
            elif hasattr(doc, 'items'):
                docs.append(dict(doc.items()))
            else:
                raise TypeError('expected dict, got %s' % type(doc))
        uri = "/%s/_bulk_docs" % self.dbName
        body = json.dumps({'docs': docs})
        headers = {"Accept": "application/json"}
        return self._request('POST', uri, body, headers)

    def infoDB(self):
        uri = '/%s/' % self.dbName
        headers = {"Accept": "application/json"}
        return self._request('GET', uri, None, headers)

    def createDB(self):
        self._request('PUT', '/%s/' % self.dbName)

    def deleteDB(self):
        uri = '/%s/' % self.dbName
        for i in xrange(5):
            # worm around a bug on windows in couch 0.9:
            # https://issues.apache.org/jira/browse/COUCHDB-326
            # We just need to wait a little and try again...
            # (after closing all outstanding connections...)
            while self.connections_available:
                self.connections_available.pop().close()
            try:
                self._request('DELETE', uri)
                # and delete the connection we just made!
                while self.connections_available:
                    self.connections_available.pop().close()
                break
            except CouchNotFoundError:
                break
            except CouchError, exc:
                if exc.status != 500:
                    raise
                if i == 4:
                    raise
                import time
                time.sleep(0.1)


    def listChanges(self, **kw):
        """Interface to the _changes feed.
        """
        # XXX - this need more work to better support feed=continuous - in
        # that case we need to process the response by line, rather than in
        # its entirity as done here and everywhere else...
        uri = "/%s/_changes" % (self.dbName,)
        # suck the kwargs in
        args = _encode_options(kw)
        if args:
            uri += "?%s" % (urlencode(args),)
        return self._request('GET', uri)
        
    def listDocsBySeq_Orig(self, **kw):
        """
        List all documents in a given database by the document's sequence number
        """
        # Response:
        # {"total_rows":1597,"offset":0,"rows":[
        # {"id":"test","key":1,"value":{"rev":"4104487645"}},
        # {"id":"skippyhammond","key":2,"value":{"rev":"121469801"}},
        # ...
        uri = "/%s/_all_docs_by_seq" % (self.dbName,)
        # suck the kwargs in
        args = _encode_options(kw)
        if args:
            uri += "?%s" % (urlencode(args),)
        return self._request('GET', uri)

    def _changes_row_to_old(self, seq):
        # Converts a row returned by _changes to a row that looks like
        # it came from _all_docs_by_seq
        last_change = seq['changes'][-1]
        row = {'id': seq['id'],
               'key': seq['seq'],
               'value': last_change, # has 'rev'
              }
        # 'deleted' was in the value
        if 'deleted' in seq:
            row['value']['deleted'] = seq['deleted']
        if 'doc' in seq:
            row['doc'] = seq['doc']
        return row

    def listDocsBySeq_Changes(self, **kw):
        """
        List all documents in a given database by the document's sequence 
        number using the _changes API.

        Transforms the results into what the old _all_docs_by_seq API
        returned, but ultimately this needs to die and move exclusively
        with the new API and new result format.
        """
        kwuse = kw.copy()
        if 'startkey' in kwuse:
            kwuse['since'] = kwuse.pop('startkey')

        result = self.listChanges(**kwuse)
        # convert it back to the 'old' format.
        rows = []
        for seq in result['results']:
            row = self._changes_row_to_old(seq)
            rows.append(row)
        return {'rows': rows}

    def listDocsBySeq(self, **kw):
        # determine what API we should use.  Note that even though _changes
        # appeared in 0.10, support for 'limit=' didn't appear until 0.11 - 
        # after _all_docs_by_seq was removed.  So we must use _all_docs_by_seq
        # if it exists.
        if self._has_adbs is None:
            try:
                ret = self.listDocsBySeq_Orig(**kw)
                self._has_adbs = True
                return ret
            except CouchNotFoundError, exc:
                self._has_adbs = False
        if self._has_adbs:
            ret = self.listDocsBySeq_Orig(**kw)
        else:
            ret = self.listDocsBySeq_Changes(**kw)
        return ret

    # *sob* - base class has no 'endkey' - plus I've renamed the param from
    # 'startKey' to 'startkey' so the same param is used with the other
    # functions which take **kw...
    # AND support for keys/POST
    def listDoc(self, **kw):
        """
        List all documents in a given database.
        """

        # Responses: {u'rows': [{u'_rev': -1825937535, u'_id': u'mydoc'}],
        # u'view': u'_all_docs'}, 404 Object Not Found
        uri = "/%s/_all_docs" % (self.dbName,)
        opts = kw.copy()
        if 'keys' in opts:
            method = 'POST'
            body_ob = {'keys': opts.pop('keys')}
            body = json.dumps(body_ob, allow_nan=False)
        else:
            method = 'GET'
            body = None
        args = _encode_options(opts)
        if args:
            uri += "?%s" % (urlencode(args),)

        headers = {"Accept": "application/json"}
        return self._request(method, uri, body, headers)

