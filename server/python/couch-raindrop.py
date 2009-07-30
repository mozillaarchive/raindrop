#! /usr/bin/env python
"""A couchdb 'external' interface to raindrop.

Accepts json requests on stdin and writes results to stdout.

Currently this never blocks for long - it kicks off any long-running processes
then returns immediately.

For general information on couchdb externals, see:
  http://wiki.apache.org/couchdb/ExternalProcesses

In summary, you must configure your couch .ini file with the following 2
entries:

  [httpd_db_handlers]
  _raindrop = {couch_httpd_external, handle_external_req, <<"raindrop">>}
  [external]
  raindrop=path/to/couch-raindrop.py --log-level=info --log-file=~/raindrop.log

Restart couch, then:

  % curl "http://127.0.0.1:5984/raindrop/_raindrop/sync-messages?protocol=skype"
  {"result":"started"}
  % curl "http://127.0.0.1:5984/raindrop/_raindrop/status
  {"running":{"sync-messages":2.9140000343322754},"finished":{}}
  ...
  % curl "http://127.0.0.1:5984/raindrop/_raindrop/status
  {"running":{},"finished":{"sync-messages":142}}
  % curl "http://127.0.0.1:5984/raindrop/_raindrop/exit
  {"result":"goodbye"}

"""
import sys
import time
import logging
import json
import threading
import traceback
import optparse
import pprint
import time
from cStringIO import StringIO

from twisted.internet import protocol, reactor, stdio, defer, threads
from twisted.python.failure import Failure
from zope.interface import implements
from twisted.internet import interfaces

from raindrop import pipeline, model, opts, config
from raindrop.sync import get_conductor

logger = logging.getLogger('raindrop')

all_commands = {} # keyed by name, value is a function returning a deferred.
running_tasks = {} # keyed by 'task name', value is a (deferred, time_started)
finished_tasks = {} # keyed by 'task name', value is some json object

class HelpFormatter(optparse.IndentedHelpFormatter):
    def format_description(self, description):
        return description


class RequestFailed(Exception):
    # Throw this exception with any json encodable object at all
    def __init__(self, code, **kw):
        self.error_ob = kw
        self.code = code
        Exception.__init__(self, code, kw)


def get_request_opts_help():
    # Get help for our 'request' options.
    info = "The following options can be encoded in each request\n" \
           "  (but don't specify the leading --)"
    hf = HelpFormatter()
    tp = optparse.OptionParser("", formatter=hf)
    og = optparse.OptionGroup(tp, info)
    for opt in opts.get_request_options():
        og.add_option(opt)
    tp.add_option_group(og)
    return tp.format_option_help(hf)

def options_from_request(req):
    def mp_error(msg): # monkey-patch!
        raise RequestFailed(400, error=msg)

    parser = optparse.OptionParser()
    parser.error = mp_error
    for opt in opts.get_request_options():
        parser.add_option(opt)
    # parse the options - the easy way - make a 'command-line'...
    argv = [''] # argv[0] - ignored...
    for name, val in req['query'].iteritems():
        if val:
            argv.append("--%s=%s" % (name, val))
        else:
            argv.append("--%s" % (name,))
    options, _ = parser.parse_args(argv)
    return options


@defer.inlineCallbacks
def _get_pipeline(req):
    opts = options_from_request(req)
    pl = pipeline.Pipeline(model.get_doc_model(), opts)
    _ = yield pl.initialize()
    defer.returnValue(pl)

def log_twisted_failure(failure, msg, *args):
    f = StringIO()
    f.write(msg % args)
    f.write("\n")
    failure.printTraceback(file=f)
    text = f.getvalue()
    logger.error(text)
    return text


def _done_async(result, key):
    if isinstance(result, Failure):
        txt = log_twisted_failure(result, "asynch task %r failed", key)
        resp = {"error": txt}
    else:
        logger.info("async task %r finished", key)
        resp = result
    finished_tasks[key] = resp
    del running_tasks[key]


def _start_async(key, func, *args, **kw):
    if key in running_tasks:
        raise RequestFailed(423, error="already running")
    d = func(*args, **kw)
    if key in finished_tasks:
        del finished_tasks[key]
    running_tasks[key] = (d, time.time())
    d.addBoth(_done_async, key)
    return {"code": 202, "json": {"result": "started"}}


# The actual commands...
def exit(req):
    """Terminate the child process.  Useful when the server has changed."""
    # easiest way to force termination is to close stdin...
    sys.stdin.close()
    return {"code": 200, "json": {"result": "goodbye"}}


def status(req):
    """request information about how things are going..."""
    running = {}
    for key, (defd, started) in running_tasks.iteritems():
        running[key] = time.time() - started
    return {"code": 200, "json": {"running": running,
                                  "finished": finished_tasks}}


def process(req):
    """process the work queues..."""
    @defer.inlineCallbacks
    def _process(req):
        pl = yield _get_pipeline(req)
        ret = yield pl.start()
        defer.returnValue(ret)

    return _start_async("process", _process, req)


def sync_messages(req):
    """Synchronize all messages from all accounts"""
    @defer.inlineCallbacks
    def _sync_messages(req):
        conductor = get_conductor()
        pl = yield _get_pipeline(req)
        conductor.options = pl.options # *sob*
        num = None
        if not pl.options.no_process:
            pl.prepare_sync_processor()
        try:
            _ = yield conductor.sync(None)
        finally:
            if not pl.options.no_process:
                num = pl.finish_sync_processor()
        defer.returnValue(num)

    return _start_async("sync-messages", _sync_messages, req)


def dispatch(req):
    if not req['path']:
        raise RequestFailed(400, error="no command specified")
    cmdname = req['path'][-1]
    try:
        command = all_commands[cmdname]
    except KeyError:
        raise RequestFailed(404, command=cmdname)

    return command(req)

# returns a deferred...
def _do_dispatch_ob(ob):
    def handle_err(failure):
        if isinstance(failure.value, RequestFailed):
            failure.raiseException()
        txt = log_twisted_failure("Failed to process request:")
        raise RequestFailed(500, error=txt)

    defd = defer.maybeDeferred(dispatch, ob)
    defd.addErrback(handle_err)
    return defd
    #try:
    #    result = dispatch(ob)
    #except RequestFailed:
    #    raise
    #except:
    #    logger.exception("failed to process request")
    #    msg = ''.join(["Failed to process request:"] +
    #                   traceback.format_exception(*sys.exc_info()))
    #    raise RequestFailed(500, error=msg)
    #return result


def dispatch_ob(ob):
    # avoid the exception handler here - it works much nicer if it is in the
    # calling thread!
    return threads.blockingCallFromThread(reactor, _do_dispatch_ob, ob)


def _do_dispatch_json(json_src):
    try:
        ob = json.loads(json_src)
    except ValueError, exc:
        msg = "Failed to decode request: %s" % exc
        raise RequestFailed(500, error=msg)
    else:
        result = dispatch_ob(ob)
    # have a 'result' object - encode it back up.
    try:
        ret = json.dumps(result)
    except ValueError, exc:
        msg = "Failed to encode response: %s" % exc
        raise RequestFailed(500, error=msg)
    return ret

def dispatch_json(json_src):
    try:
        return _do_dispatch_json(json_src)
    except RequestFailed, exc:
        ret_ob = {"code": exc.code, "json": exc.error_ob}
        return json.dumps(ret_ob) 


def stdio_interact():
    if sys.stdout.isatty() and sys.stdin.isatty():
        print "running interactively - enter an empty line to terminate..."
    while 1:
        try:
            got = sys.stdin.readline().strip()
        except ValueError:
            logger.info("stdin closed - terminating")
            break
        if not got:
            print "no request found - terminating"
            break
        sys.stdout.write(dispatch_json(got)+"\n")
        sys.stdout.flush()
    reactor.stop()

def stdio_one():
    got = sys.stdin.read()
    ret_json = dispatch_json(got)
    # pprint the object back out.
    ret_ob = json.loads(ret_json)
    pprint.pprint(ret_ob)
    #sys.stdout.write()
    reactor.callLater(0, reactor.stop)

def main():
    descs = []
    for n, v in globals().iteritems():
        if callable(v) and getattr(v, '__doc__', None) and v.__module__==__name__:
            all_commands[n.replace('_', '-')] = v
            descs.append("%s:" % n)
            descs.append("  %s" % v.__doc__)

    description = '\n'.join([__doc__, 'Commands:', '']+descs) + '\n' + \
                  get_request_opts_help()
    parser = optparse.OptionParser("%prog [options]",
                                   description=description,
                                   formatter=HelpFormatter())
    for opt in opts.get_program_options():
        parser.add_option(opt)

    # For testing...
    parser.add_option("", "--one", action="store_true",
            help="Only process one request and exit; accepts multi-line "
                 "input and emits multi-line, pretty-printed output.")

    options, args = parser.parse_args()
    if args: # later may accept input filenames for testing?
        parser.error("this program accepts no args")

    opts.setup_logging(options)
    config.init_config()

    # create an initial deferred to perform tasks which must occur before we
    # can start.  The final callback added will fire up the real servers.
    d = defer.Deferred()

    def start_stdio(whateva):
        # using twisted's stdio is just way too hard on windows - just use a
        # dedicated thread...
        if options.one:
            target = stdio_one
        else:
            target = stdio_interact
        t = threading.Thread(target=target)
        t.start()
    d.addCallback(start_stdio)

    def done(whateva):
        pass

    def error(failure):
        log_twisted_failure(failure, "unhandled top-level error?")
#        reactor.stop()

    d.addCallbacks(done, error)
    
    reactor.callWhenRunning(d.callback, None)
    reactor.run()

if __name__ == "__main__":
    main()
