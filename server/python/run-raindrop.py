#!/usr/bin/env python
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

"""The raindrop server
"""
from __future__ import with_statement

import sys
import optparse
import logging
import datetime
import time
import webbrowser
import threading
try:
    import json # standard module in python 2.6+
except ImportError:
    import simplejson as json # external module in 2.5 and earlier

from raindrop import model
from raindrop import bootstrap
from raindrop import pipeline
from raindrop import opts
from raindrop import proto
from raindrop.sync import get_conductor
from raindrop.config import get_config, init_config

logger = logging.getLogger('raindrop')

g_pipeline = None
g_conductor = None

class HelpFormatter(optparse.IndentedHelpFormatter):
    def format_description(self, description):
        return description

# decorators for our global functions:
#  so they can consume the rest of the args
def allargs_command(f):
    f.allargs = True
    return f


# XXX - install_accounts should die too, but how to make a safe 'fingerprint'
# so we can do it implicitly? We could create a hash which doesn't include
# the password, but then the password changing wouldn't be enough to trigger
# an update.  Including even the *hash* of the password might risk leaking
# info.  So for now you must install manually.
def install_accounts(parser, options):
    """Install accounts in the database from the config file"""
    return bootstrap.install_accounts(None)


def _call_api(dbconfig, path):
    db = model.get_doc_model().db
    host = dbconfig['host']
    port = dbconfig['port']
    dbname = dbconfig['name']
    uri = "http://%s:%s/%s/%s" % (host, port, dbname, path)
    return  db._request("GET", uri)


def show_info(parser, options):
    """Print a list of all extensions, loggers etc"""
    dm = model.get_doc_model()
    print "Database:"
    info = dm.db.infoDB()
    fmt = "  %(doc_count)d docs total, %(doc_del_count)d deleted, " \
          "update seq at %(update_seq)d, %(disk_size)d bytes."
    print fmt % info
    # ouch - this seems a painful way of fetching total unique keys?
    results = dm.open_view(
                startkey=["key"],
                endkey=["key", {}],
                group_level=2)
    print "  %d unique raindrop keys" % len(results['rows'])

    print "API groupings:"
    from urllib import urlencode
    dbconfig = get_config().couches['local']
    try:
        summaries = _call_api(dbconfig, "_api/inflow/grouping/summary")
        print " %d groupings exist" % len(summaries)
        for gs in summaries:
            title = gs.get('title') or gs['rd_key']
            opts = {'limit': 60, 'message_limit': 2,
                    'keys': json.dumps([gs['rd_key']]),
                    }
            path = "_api/inflow/conversations/in_groups?" + urlencode(opts)
            this = _call_api(dbconfig, path)
            print "  %s: %d conversations" % (title, len(this))
    except dm.db.Error, exc:
        print "Failed to call the API:", exc
    
    print "Document counts by schema:"
    results = dm.open_view(
                startkey=["schema_id"],
                endkey=["schema_id", {}],
                group_level=2)
    infos = []
    for row in results['rows']:
        sch_id = row['key'][-1]
        infos.append((sch_id, row['value']))
    for sch_id, count in sorted(infos):
        print "  %s: %d" % (sch_id, count)
    print

    print "Raindrop extensions:"
    exts = sorted((pipeline.load_extensions(dm)).items()) # sort by ID.
    for _, ext in exts:
        print "  %s: %s" % (ext.id, ext.doc['info'])
    print
    print "Loggers"
    # yuck - reach into impl - and hope all have been initialized by now
    # (they should have been as we loaded the extensions above)
    for name in logging.Logger.manager.loggerDict:
        print " ", name

def _safe_run(fn, *args):
    try:
        fn(*args)
    except Exception:
        logger.exception("%r failed", fn)

def sync_messages(parser, options, **kw):
    """Synchronize all messages from all accounts"""
    state = {'finished': False}
    def stable(seq):
        if state['finished']:
            return True

    def _do_sync():
        g_conductor.sync(options, **kw)
        g_conductor.wait_for_sync()
        state['finished'] = True

    def _do_process():
        callback = None
        # if 'continuous' is not specified we want to terminate as soon
        # as the queue becomes 'stable' after syncing.
        if not options.continuous:
            callback = stable
        g_pipeline.start_processing(callback)
        
    # fire them up
    process_thread = None
    if not options.no_process:
        process_thread = threading.Thread(target=_safe_run, args=(_do_process,))
        process_thread.setDaemon(True)
        process_thread.start()
    else:
        if options.continuous:
            parser.error("--no-process can't be used with --continuous")

    # and this bit of work can just be done in the main thread...
    _do_sync()
    if process_thread is not None:
        logger.info("waiting for processing to complete...")
        process_thread.join()


def sync_incoming(parser, options):
    """Synchronize all incoming messages from all accounts"""
    return sync_messages(result, parser, options, incoming=True, outgoing=False)

def sync_outgoing(parser, options):
    """Synchronize all outgoing messages from all accounts"""
    return sync_messages(result, parser, options, incoming=False, outgoing=True)

def process(parser, options):
    """Process all messages to see if any extensions need running"""
    def should_stop(seq):
        return not options.continuous
    result = g_pipeline.start_processing(should_stop)
    print "Message pipeline has finished - created", result, "docs"

def process_backlog(parser, options):
    "deprecated - please use 'process'"
    logger.warn("The 'process-backlog' command is deprecated.  Please use 'process'.")
    return process(result, parser, options)

def reprocess(parser, options):
    """Reprocess all messages even if they are up to date."""
    g_pipeline.reprocess()
    print "Message pipeline has finished..."

def retry_errors(parser, options):
    """Reprocess all conversions which previously resulted in an error."""
    g_pipeline.start_retry_errors()
    print "Error retry pipeline has finished..."
    # Now reset all outgoing items with a state of 'error' back to 'outgoing'
    dm = model.get_doc_model()
    result = dm.open_view(viewId="outgoing_by_state", key="error",
                          include_docs=True)
    docs = [r['doc'] for r in result['rows']]
    if docs:
        for d in docs:
            d['outgoing_state'] = 'outgoing'
        dm.update_documents(docs)
    print "Reset %d outgoing items for retry" % (len(docs),)
    # XXX - should do the 'process' thing now...

@allargs_command
def show_view(parser, options, args):
    """Pretty-print the result of executing a view.

    All arguments after this command are URLs to be executed as the view.  If
    the view name starts with '/', the URL will be used as-is.  This is
    suitable for builtin views - eg:

        show-view /_all_docs?limit=5
    
    will fetch the first 5 results from the URL:

        http://[dbhost]/[dbname]/_all_docs?limit=5"

    whereas

        show-view my_design_doc/my_view?limit=5

    will fetch the first 5 results from the URL

        http://[dbhost]/[dbname]/_design/my_design_doc/_view/my_view?limit=5

    """
    from pprint import pprint

    for arg in args:
        # don't use open_view as then we'd need to parse the query portion!
        # grrr - just to get the dbname :()
        dbinfo = get_config().couches['local']
        dbname = dbinfo['name']
        if arg.startswith("/"):
            uri = "/%s/%s" % (dbname, arg)
        else:
            try:
                doc, rest = arg.split("/")
            except ValueError:
                parser.error("View name must be in the form design_doc_name/view")
            uri = "/%s/_design/%s/_view/%s" % (dbname, doc, rest)
        db = model.get_db()
        result = db.get(uri)
        print "** view %r **" % arg
        pprint(result)


def unprocess(parser, options):
    """Delete all documents which can be re-generated by the 'process' command
    """
    return g_pipeline.unprocess()
    print "unprocess has finished..."

@allargs_command
def add_schemas(parser, options, args):
    """Add one or more schema documents to the couch"""
    if not args:
        parser.error("You must supply filenames containing json for the docs")
    dm = model.get_doc_model()
    for arg in args:
        try:
            with open(arg) as f:
                try:
                    vals = json.load(f)
                except ValueError, why:
                    parser.error("file %r has invalid json: %s" % (arg, why))
        except IOError:
            parser.error("Failed to open json document %r" % arg)

        got = dm.create_schema_items([vals])
        print "Saved doc id %(id)r at rev %(rev)s" % got[0]

def delete_docs(parser, options):
    """Delete all documents of a particular type.  Use with caution or see
       the 'unprocess' command for an alternative.
    """
    # NOTE: This is for development only, until we get a way to say
    # 'reprocess stuff you've already done' - in the meantime deleting those
    # intermediate docs has the same result...
    def _del_docs(to_del):
        docs = []
        for id, rev in to_del:
            docs.append({'_id': id, '_rev': rev})
        return model.get_doc_model().delete_documents(docs)

    def _got_docs(result, dt):
        to_del = [(row['id'], row['value']['_rev']) for row in result['rows']]
        logger.info("Deleting %d documents of type %r", len(to_del), dt)
        return to_del

    if not options.schemas:
        parser.error("You must specify one or more --schema")
    for st in options.schemas:
        key = ['schema_id', st]
        result = model.get_doc_model().open_view(key=key, reduce=False)
        to_del = _got_docs(result, st)
        _del_docs(to_del)


def main():
    # build the args we support.
    start = datetime.datetime.now()
    all_args = {}
    for n, v in globals().iteritems():
        # explicit check for functions so other globals don't match..
        if type(v)==type(main) and getattr(v, '__doc__', None):
            all_args[n.replace('_', '-')] = v

    all_arg_names = sorted(all_args.keys())
    description= __doc__ + "\nCommands\n  help\n  " + \
                 "\n  ".join(all_args.keys()) + \
                 "\nUse '%prog help command-name' for help on a specific command.\n"

    parser = optparse.OptionParser("%prog [options]",
                                   description=description,
                                   formatter=HelpFormatter())

    for opt in opts.get_program_options():
        parser.add_option(opt)
    for opt in opts.get_request_options():
        parser.add_option(opt)
    options, args = parser.parse_args()

    opts.setup_logging(options)

    init_config(options.config)
    proto.init_protocols()

    # patch up keys.
    if options.keys:
        def _fix_unicode(result):
            if isinstance(result, list):
                for i, v in enumerate(result):
                    result[i] = _fix_unicode(result[i])
            elif isinstance(result, unicode):
                result = result.encode('utf-8')
            return result
        for i, val in enumerate(options.keys):
            try:
                # help windows - replace single quote with double...
                val = val.replace("'", '"')
                options.keys[i] = _fix_unicode(json.loads(val))
            except ValueError, why:
                parser.error("Invalid key value %r: %s" % (val, why))

    if args and args[0]=='help':
        if args[1:]:
            which = args[1:]
        else:
            which = all_args.keys()
        for this in which:
            if this=='help': # ie, 'help help'
                doc = "show help for the commands."
            else:
                try:
                    doc = all_args[this].__doc__
                except KeyError:
                    print "No such command '%s':" % this
                    continue
            print "Help for command '%s':" % this
            print doc
            print
    
        sys.exit(0)

    print "Raindrops keep falling on my head..."
    try:
        model.fab_db()
        # See if accounts are up-to-date.
        if not options.no_bootstrap:
            bootstrap.install_views(options)
            bootstrap.check_accounts()
            # Check if the files on the filesystem need updating.
            bootstrap.install_client_files(options)
            bootstrap.insert_default_docs(options)
            bootstrap.update_apps()

        global g_pipeline, g_conductor
        assert g_pipeline is None and g_conductor is None
        g_pipeline = pipeline.Pipeline(model.get_doc_model(), options)
        g_pipeline.initialize()
        g_conductor = get_conductor(g_pipeline)

        # Now process the args specified.
        for i, arg in enumerate(args):
            try:
                func = all_args[arg]
            except KeyError:
                parser.error("Invalid command: " + arg)

            consumes_args = getattr(func, 'allargs', False)
            if consumes_args:
                func(parser, options, args[i+1:])
                break
            else:
                func(parser, options)

        g_pipeline.finalize()
    except SystemExit:
        pass
    except KeyboardInterrupt:
        print "Interrupted"
    except:
        print "A command failed - terminating."
        raise   

    print "raindrops were falling for", str(datetime.datetime.now()-start)


if __name__=='__main__':
    main()
