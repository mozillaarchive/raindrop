#! /usr/bin/env python
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

"""A couchdb REST API runner for raindrop.

Accepts json requests on stdin and writes results to stdout.  Loads,
compiles and executes API end-points from couch documents depending on the
request URL.
"""

import sys
import httplib
from time import time
from urllib import urlencode, quote
import optparse

from raindrop import json
from raindrop import config

# -- library code --
# The short-term intention is to move to javascript based API implementations
# The javascript environment will have available a number of utility classes,
# the most important being the 'CouchDB' class.
# Below are some utilities all Python implemented API functions have available
# in their globals
api_globals={'json': json}

# A little hack so we can record some basic perf stats about certain things
# if specified on the cmdline.  This function may be overridden in main()
# by the do_note_timeline function
note_timeline = lambda msg, *args: None

def do_note_timeline(msg, *args):
    msg = msg % args
    log("%.3f: %s", time(), msg)

def get_api_config_filename(req):
    dbname = req['path'][0]
    return "~/." + dbname

def get_api_config(req):
    return config.Config(get_api_config_filename(req))

api_globals['get_api_config_filename'] = get_api_config_filename
api_globals['get_api_config'] = get_api_config

class API:
    # A base class - helpers for the implementation classes...
    def get_args(self, req, *req_args, **opt_args):
        _json = True
        if '_json' in opt_args:
            _json = opt_args.pop('_json')
        supplied = {}
        for name, val in req['query'].iteritems():
            if _json:
                try:
                    val = json.loads(val)
                except ValueError, why:
                    raise APIErrorResponse(400, "invalid json in param '%s': %s" % (name, why))
            supplied[name] = val

        body = req.get('body')
        if _json and body and body != 'undefined': # yes, couch 0.10 send the literal 'undefined'
            # If there was a body specified, it can also contain request
            # args - although no args can be specified in both places.
            try:
                body_args = json.loads(body)
                if not isinstance(body_args, dict):
                    raise ValueError, "body must be a json object"
            except ValueError, why:
                raise APIErrorResponse(400, "invalid json in request body: %s" % (why,))
            s = set(body_args)
            both = s.intersection(set(supplied))
            if both:
                msg = "the following arguments appear in both the query string and post body: %s" \
                      % (",".join(both))
                raise APIErrorResponse(400, msg)
            supplied.update(body_args)

        ret = {}
        for arg in req_args:
            if arg not in supplied:
                raise APIErrorResponse(400, "required argument '%s' missing" % arg)
            ret[arg] = supplied[arg]
        for arg, default in opt_args.iteritems():
            try:
                val = supplied[arg]
            except KeyError:
                val = default
            ret[arg] = val
        # now check there aren't extra unknown args
        for arg in supplied.iterkeys():
            if arg not in ret:
                raise APIErrorResponse(400, "unknown request argument '%s'" % arg)
        return ret

    def _requires_verbs(self, req, verbs):
        try:
            method = req['method'] # couch 0.11+
        except KeyError:
            method = req['verb'] # 0.10
        if method not in verbs:
            if len(verbs)==1:
                msg = "%s required" % (verbs[0])
            else:
                msg = "one of %s or %s required" % (",".join(verbs[:-1]), verb[-1])
            raise APIErrorResponse(405, msg)

    def requires_get(self, req):
        self._requires_verbs(req, ['GET'])

    def requires_post(self, req):
        self._requires_verbs(req, ['POST'])

    def requires_get_or_post(self, req):
        self._requires_verbs(req, ['GET', 'POST'])

    def _filter_user_fields(self, doc):
        ret = {}
        for attr, val in doc.iteritems():
            if not attr.startswith('rd_') and not attr.startswith('_'):
                ret[attr] = val
        return ret

    def absuri(self, db, path):
        # kinda like abspath, but makes a URL absolute based on our raindrop
        # location and port name.
        # this is very very hacky...
        host = db.connection.host
        port = db.connection.port or 80
        return ("http://%s:%s" % (host, port)) + db.uri + path

api_globals['API'] = API

# Function that handles dispatching requests to API subclasses.
# Only used by top-level API endpoints.
def api_handle(request, dispatch):
    try:
        # the 'path' tells us the end-point.  It is [db, external, app, class, method]
        # and our caller has already checked it has exactly that many elts...
        assert len(request['path'])==5, request
        cls, meth_name = request['path'][-2:]
        if cls not in dispatch:
            raise APIErrorResponse(400, "invalid API request endpoint class")
        # fetch the names method from the class instance
        inst = dispatch[cls]
        meth = getattr(inst, meth_name, None)
        # check it is callable etc.
        if not callable(meth) or meth_name.startswith('_'):
            raise APIErrorResponse(400, "invalid API request endpoint function: '%s'" % (meth_name))
        # phew - call it.
        resp = meth(request)
        if ('_raw_methods' in dispatch and meth_name in dispatch['_raw_methods']):
            resp = make_response(resp[0], resp[1], resp[2])
        else:
            resp = make_response(resp)
    except APIException, exc:
        resp = exc.err_response
        log("error response: %s", resp)
    except Exception, exc:
        import traceback, StringIO
        s = StringIO.StringIO()
        traceback.print_exc(file=s)
        resp = make_response(s.getvalue(), 400)
        log("exception response: %s", resp)
    return resp

api_globals['api_handle'] = api_handle


# This is a port of some of the couch.js class.
class CouchDB:
    default_host = None
    default_port = None
    def __init__(self, name, host=None, port=None):
        self.name = name;
        self.uri = "/" + quote(name) + "/"
        # share and reuse one connection.
        self.connection = httplib.HTTPConnection(host or self.default_host,
                                                 port or self.default_port)

    def maybeThrowError(self, resp):
        if resp.status >= 400:
            text = resp.read()
            try:
                result = json.loads(text)
            except ValueError:
                raise APIErrorResponse(400, text)
            raise APIErrorResponse(resp.status, result)
        # strange - couch.js doesn't check any other conditions?

    def request(self, method, uri, headers={}, body=None):
        c = self.connection
        c.request(method, uri, body, headers)
        return c.getresponse()

    def view(self, viewname, **kw):
        # The javascript impl has a painful separation of the 'keys' param
        # from other params - hide that.
        kw = kw.copy()
        keys = kw.get('keys')
        if keys is not None:
            del kw['keys']
        # stale is a little tricky - 'ok' is the only valid option.  So if
        # the user puts 'stale=None' we assume stale is *not* ok!
        if 'stale' in kw:
            stale = kw['stale']
            assert stale in (None, 'ok'), stale # only ok and None are allowed!
            if stale is None:
                del kw['stale']
        else:
            kw['stale'] = 'ok'
        viewParts = viewname.split('/')
        viewPath = self.uri + "_design/" + viewParts[0] + "/_view/" \
            + viewParts[1] + self.encodeOptions(kw)
        if keys is None:
            resp = self.request("GET", viewPath);
        else:
            resp = self.request("POST", viewPath,
                                headers={"Content-Type": "application/json"},
                                body=json.dumps({'keys':keys}))

        if resp.status == 404:
          return None
        self.maybeThrowError(resp)
        return json.load(resp);

    # Args here are different than js - pythonic makes more sense...
    def allDocs(self, keys, **options):
        assert keys, "don't call me if you don't want any docs!"
        uri = self.uri + "_all_docs" + self.encodeOptions(options)
        resp = self.request("POST", uri,
                            headers={"Content-Type": "application/json"},
                            body=json.dumps({'keys':keys}))
        self.maybeThrowError(resp)
        return json.load(resp);

    # Convert a options object to an url query string.
    # ex: {key:'value',key2:'value2'} becomes '?key="value"&key2="value2"'
    def encodeOptions(self, options):
        use = {}
        for name, value in options.iteritems():
            if name in ('key', 'startkey', 'endkey', 'include_docs') \
                    or not isinstance(value, basestring):
                value = json.dumps(value, allow_nan=False)
            use[name] = value
        if not use:
            return ''
        return "?" + urlencode(use)

api_globals['CouchDB'] = CouchDB

def log(msg, *args):
    print json.dumps(["log", (msg % args)])

api_globals['log'] = log

# helper functions exposed to the API
from raindrop.model import DocumentModel
api_globals['hashable_key'] = DocumentModel.hashable_key
api_globals['get_doc_id_for_schema_item'] = DocumentModel.get_doc_id_for_schema_item

# -- raindrop specific APIs
class RDCouchDB(CouchDB):
    def __init__(self, req):
        name = req['path'][0] # first elt of path is db name
        host = req.get('peer') # later couchdb versions include this...
        port = None # XXX - get the 'port' from the request too (but it isn't provided now!)
        CouchDB.__init__(self, name, host, port)

    def megaview(self, **kw):
        note_timeline("megaview request opts=%s, %d keys", kw, len(kw.get('keys') or []))
        # and make the request.
        ret = self.view('raindrop!content!all/megaview', **kw)
        note_timeline("megaview result - %d rows", len(ret['rows']))
        return ret

api_globals['RDCouchDB'] = RDCouchDB

def make_response(result, code=None, headers=None):
    # create the json response object couchdb expects.
    ob = {'json' : result}
    if code is not None:
        ob['code'] = code
    if headers is not None:
        ob['headers'] = headers
    return ob

api_globals['make_response'] = make_response

# a couple of exceptions...
class APIException(Exception):
    def __init__(self, err_response):
        self.err_response = err_response
        Exception.__init__(self)

api_globals['APIException'] = APIException

class APIErrorResponse(APIException):
    def __init__(self, code, message):
        resp = make_response( {'error': code, 'reason': message}, code=code)
        APIException.__init__(self, resp)

api_globals['APIErrorResponse'] = APIErrorResponse

# -- api runner code --

class APILoadError(Exception):
    def __init__(self, msg, *args):
        self.msg = msg = msg % args
        Exception.__init__(self)

# REST end-point handlers we have already loaded.
_handlers = {}

def get_api_handler(options, req):
    # path format is "db_name/external_name/app_name/class_name/method_name
    if len(req.get('path', [])) != 5:
        raise APILoadError("invalid api request format")
    dbname = req['path'][0]
    cache_key = tuple(req['path'][:4])
    try:
        return _handlers[cache_key]
    except KeyError:
        # first request for this handler
        pass

    # Load the schemas which declare they implement this end-point
    apiid = req['path'][2:4] # the 'app' name and the 'class' name.
    path = "/%s/_design/raindrop!content!all/_view/api_endpoints" % dbname
    req_options = {'key': json.dumps(apiid), 'include_docs': 'true'}
    uri = path + "?" + urlencode(req_options)

    c = httplib.HTTPConnection(options.couchdb_host, options.couchdb_port)
    c.request("GET", uri)
    resp = c.getresponse()
    if resp.status != 200:
        raise APILoadError("api query failure (%s: %s) to %s:%s", resp.status,
                           resp.reason, options.couchdb_host, options.couchdb_port)
    result = json.load(resp)
    resp.close()
    rows = result['rows']
    if not rows:
        raise APILoadError("No such API end-point %s", apiid)
    if len(rows) != 1: # should only be one doc with this criteria!
        raise APILoadError("too many docs say they implement this api!")
    doc = rows[0]['doc']
    if doc.get('content_type') != 'application/x-python' or not doc.get('code'):
        raise APILoadError("document is not a python implemented API (%s)", doc['content_type'])

    # Now dynamically compile the code we loaded.
    globs = api_globals.copy()
    try:
        exec doc['code'] in globs
    except Exception, exc:
        raise APILoadError("Failed to initialize api: %s", exc)
    handler = globs.get('handler')
    if handler is None or not callable(handler):
        raise APILoadError("source-code in extension doesn't have a 'handler' function")
    _handlers[cache_key] = handler
    log("loaded API end-point %s from %r", cache_key, doc['_id'])
    return handler

def process(req, options):
    # handle 'special' requests'
    if len(req['path'])==3 and req['path'][-1] == '_reset':
        msg = '%d document(s) dropped' % len(_handlers)
        resp = {'code': 200, 'json': {'info': msg}}
        _handlers.clear()
    elif len(req['path'])==3 and req['path'][-1] == '_exit':
        json.dump({'code': 200, 'json': {'info': 'goodbye'}}, sys.stdout)
        sys.stdout.write("\n")
        sys.stdout.flush()
        sys.exit(0)
    else:
        try:
            handler = get_api_handler(options, req)
        except APILoadError, exc:
            log("%s", exc.msg)
            resp = {'code': 400, 'json': {'error': 400, 'reason': exc.msg}}
        else:
            # call the API handler - we expect the API to be robust and
            # catch mostexceptions, so if we see one, we just die.
            note_timeline("api request: %s", req['path'])
            resp = handler(req)
            note_timeline("api back")
    return resp
    
def main():
    # for now, so we know the couch defaults
    cfg = config.init_config().couches['local']
    parser = optparse.OptionParser("%prog [options]",
                                   description="the raindrop api runner")
    parser.add_option("", "--couchdb-host",
                help="Specifies the hostname to use for couchdb requests",
                default=cfg['host'])

    parser.add_option("", "--couchdb-port",
                help="Specifies the port number to use for couchdb requests",
                default=cfg['port'])

    parser.add_option("", "--show-perf", action="store_true",
                help="Reports some information about how long some things take")

    options, args = parser.parse_args()

    # no args used
    if len(args) != 0:
        print >> sys.stderr, __doc__
        print >> sys.stderr, "this program takes no arguments"
        sys.exit(1)

    if options.show_perf:
        global note_timeline
        note_timeline = do_note_timeline
    CouchDB.default_host = options.couchdb_host
    CouchDB.default_port = options.couchdb_port

    log("raindrops keep falling on my api...")
    # and now the main loop.
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        req = json.loads(line)
        resp = process(req, options)

        json.dump(resp, sys.stdout)
        sys.stdout.write("\n")
        sys.stdout.flush()
    log("raindrop api runner terminating normally")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        # likely couch itself is closing...
        sys.stderr.write('raindrop api runner interrupted...\n')
