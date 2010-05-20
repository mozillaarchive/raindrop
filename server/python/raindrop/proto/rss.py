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

# A simple RSS 'protocol'; simply manages updating a document with the raw
# data from the feed - extensions then do all the heavy lifting.

import logging
from ..proc import base
from urlparse import urlparse
import httplib2

logger = logging.getLogger(__name__)

def maybe_update_doc(conductor, doc_model, doc, options):
    uri = doc['uri'].encode("utf-8")
    parsed = urlparse(uri)
    # If we have existing content for the item, make a conditional request.
    req_headers = {}
    if not options.force and 'headers' in doc:
        doc_headers = doc['headers']
        if 'date-modified' in doc_headers:
            req_headers['If-Modified-Since'] = \
                    doc_headers['date-modified'].encode('utf-8')
        if 'etag' in doc_headers:
            req_headers['If-None-Match'] = doc_headers['etag'].encode('utf-8')

    # Issue the request.
    if parsed.scheme != 'http':
        logger.error("Can't fetch URI %r - unknown scheme", uri)
        return

    # Note we *must* use the full uri here and not just the path portion
    # or getsatisfaction returns invalid urls...
    try:
        conn = httplib2.Http()
        response, content = conn.request(uri, headers=req_headers)
    except Exception:
        logger.exception("fetching rss feed %r failed", uri)
        return

    if response.status == 304:
        # yay - nothing to update!
        logger.info('rss feed %r is up-to-date', uri)
        response.close()
        return

    if response.status != 200:
        logger.exception("bad response fetching rss feed %r: %s (%s)",
                         uri, response.status, response.reason)
        return
    logger.debug('rss feed %r has changed', uri)
    # update the headers.
    items = {
        'headers': response.copy()
    }
    a = {}
    a['response'] = {'content_type': items['headers']['content-type'],
                     'data': content}
    si = doc_model.doc_to_schema_item(doc)
    si['items'] = items
    si['attachments'] = a
    si['_rev'] = doc['_rev']
    conductor.provide_schema_items([si])
    logger.info('updated feed %r', uri)


class RSSAccount(base.AccountBase):
    def startSync(self, conductor, options):
        # Find all RSS documents.
        key = ['schema_id', 'rd.raw.rss']
        result = self.doc_model.open_view(key=key, reduce=False,
                                                 include_docs=True)
        rows = result['rows']
        logger.info("have %d rss feeds to check", len(rows))
        dl = []
        # XXX - should do these in parallel...
        for row in rows:
            doc = row['doc']
            if doc.get('disabled', False):
                logger.debug('rss feed %(id)r is disabled - skipping', row)
                continue
            maybe_update_doc(conductor, self.doc_model, doc, options)

    def get_identities(self):
        return []
