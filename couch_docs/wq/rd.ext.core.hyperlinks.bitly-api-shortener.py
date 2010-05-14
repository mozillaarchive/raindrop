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

import re
import urllib2
from raindrop import json

SERVICES = {
  "su.pr" : {
   'link_prop'            : 'path',
   'regex'                : re.compile('^/(\w+)'),
   'api'                  : "http://su.pr/api/expand",
   'hash_option_function' : lambda link, hash: link,
   'hash_option_name'     : 'shortUrl',
   'options' : { },
   'schema' : {'short_url'     : lambda link, schema: link.get('url'),
               'long_url'      : lambda link, schema: schema.get('longUrl'),
               'title'         : lambda link, schema: schema.get('longUrl'),
               'thumbnail'     : lambda link, schema: None,
               'user_name'     : lambda link, schema: link.get('domain'),
               'display_name'  : lambda link, schema: None,
               'user_url'      : lambda link, schema: None,
               'description'   : lambda link, schema: None,
               }
   },
  "bit.ly" : {
   'link_prop'            : 'path',
   'regex'                : re.compile('^/(\w+)'),
   'api'                  : "http://api.bit.ly/info",
   'hash_option_function' : lambda link, hash: hash,
   'hash_option_name'     : 'hash',
   'options' : {'version' : '2.0.1',
                'login'   : 'bitlyapidemo', # demo API user
                'apiKey'  : 'R_0da49e0a9118ff35f52f629d2d71bf07', # demo API key
                },
    'schema' : {'short_url'     : lambda link, schema: link.get('url'),
                'long_url'      : lambda link, schema: schema.get('longUrl'),
                'title'         : lambda link, schema: schema.get('htmlTitle'),
                'thumbnail'     : lambda link, schema: schema.get('thumbnail', { 'small' : None }).get('small'),
                'user_name'     : lambda link, schema: schema.get('shortenedByUser'),
                'display_name'  : lambda link, schema: schema.get('shortenedByUser'),
                'user_url'      : lambda link, schema: "http://%s/user/recent/%s" % (link.get('domain'), schema.get('shortenedByUser')),
                'description'   : lambda link, schema: schema.get('htmlMetaDescription')
                }
  },
  "bitly.com" : {
   'link_prop'            : 'path',
   'regex'                : re.compile('^/(\w+)'),
   'api'                  : "http://api.bit.ly/info",
   'hash_option_function' : lambda link, hash: hash,
   'hash_option_name'     : 'hash',
   'options' : {'version' : '2.0.1',
                'login'   : 'bitlyapidemo', # demo API user
                'apiKey'  : 'R_0da49e0a9118ff35f52f629d2d71bf07', # demo API key
                },
    'schema' : {'short_url'     : lambda link, schema: link.get('url'),
                'long_url'      : lambda link, schema: schema.get('longUrl'),
                'title'         : lambda link, schema: schema.get('htmlTitle'),
                'thumbnail'     : lambda link, schema: schema.get('thumbnail', { 'small' : None }).get('small'),
                'user_name'     : lambda link, schema: schema.get('shortenedByUser'),
                'display_name'  : lambda link, schema: schema.get('shortenedByUser'),
                'user_url'      : lambda link, schema: "http://%s/user/recent/%s" % (link.get('domain'), schema.get('shortenedByUser')),
                'description'   : lambda link, schema: schema.get('htmlMetaDescription')
                }
  },
  "j.mp" : {
   'link_prop'            : 'path',
   'regex'                : re.compile('^/(\w+)'),
   'api'                  : "http://api.bit.ly/info",
   'hash_option_function' : lambda link, hash: hash,
   'hash_option_name'     : 'hash',
   'options' : {'version' : '2.0.1',
                'login'   : 'bitlyapidemo', # demo API user
                'apiKey'  : 'R_0da49e0a9118ff35f52f629d2d71bf07', # demo API key
                },
    'schema' : {'short_url'     : lambda link, schema: link.get('url'),
                'long_url'      : lambda link, schema: schema.get('longUrl'),
                'title'         : lambda link, schema: schema.get('htmlTitle'),
                'thumbnail'     : lambda link, schema: schema.get('thumbnail', { 'small' : None }).get('small'),
                'user_name'     : lambda link, schema: schema.get('shortenedByUser'),
                'display_name'  : lambda link, schema: schema.get('shortenedByUser'),
                'user_url'      : lambda link, schema: "http://%s/user/recent/%s" % (link.get('domain'), schema.get('shortenedByUser')),
                'description'   : lambda link, schema: schema.get('htmlMetaDescription')
                }
  },
  "nyti.ms" : {
   'link_prop'            : 'path',
   'regex'                : re.compile('^/(\w+)'),
   'api'                  : "http://api.bit.ly/info",
   'hash_option_function' : lambda link, hash: hash,
   'hash_option_name'     : 'hash',
   'options' : {'version' : '2.0.1',
                'login'   : 'bitlyapidemo', # demo API user
                'apiKey'  : 'R_0da49e0a9118ff35f52f629d2d71bf07', # demo API key
                },
    'schema' : {'short_url'     : lambda link, schema: link.get('url'),
                'long_url'      : lambda link, schema: schema.get('longUrl'),
                'title'         : lambda link, schema: schema.get('htmlTitle'),
                'thumbnail'     : lambda link, schema: schema.get('thumbnail', { 'small' : None }).get('small'),
                'user_name'     : lambda link, schema: schema.get('shortenedByUser'),
                'display_name'  : lambda link, schema: schema.get('shortenedByUser'),
                'user_url'      : lambda link, schema: None,
                'description'   : lambda link, schema: schema.get('htmlMetaDescription')
                }
  },
}

def handler(doc):
    link = doc
    hash = None
    service = SERVICES.get(link['domain'], None)
    if service is not None:
        prop = service.get('link_prop')
        match = service.get('regex').search(link[prop])
        if match and match.group(1):
            hash = match.group(1)

    if hash is None:
        return
    service = SERVICES.get(link['domain'])

    options = service.get('options')
    options[service.get('hash_option_name')] = service.get('hash_option_function')(link['url'],hash)

    api = "%s?%s" % (service.get('api'), "&".join(['%s=%s' % v for v in options.items()]))

    opener = urllib2.build_opener()
    obj = json.load(opener.open(api))
    if obj.get('errorCode') == 0:
        shorty = obj.get('results').get(hash)
        ss = service.get("schema")
        # XXX not all of these items are actually used, we could trim down
        # the size of these documents if space needed to be saved but for
        # now it's nice to have the extra data in case we want it later
        schema = {"short_url"    : ss.get("short_url")(link, shorty),
                  "long_url"     : ss.get("long_url")(link, shorty),
                  "title"        : ss.get("title")(link, shorty),
                  "thumbnail"    : ss.get("thumbnail")(link, shorty),
                  "user_name"    : ss.get("user_name")(link, shorty),
                  "display_name" : ss.get("display_name")(link, shorty),
                  "user_url"     : ss.get("user_url")(link, shorty),
                  "description"  : ss.get("description")(link, shorty),
                  "extra"        : shorty,
                  "domain"       : link.get('domain'),
                  "ref_link"     : link['url']
                  }
        emit_schema('rd.attach.link.expanded', schema)
