# ***** BEGIN LICENSE BLOCK *****
# * Version: MPL 1.1
# *
# * The contents of this file are subject to the Mozilla Public License Version
# * 1.1 (the "License"); you may not use this file except in compliance with
# * the License. You may obtain a copy of the License at
# * http://www.mozilla.org/MPL/
# *
# * Software distributed under the License is distributed on an "AS IS" basis,
# * WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# * for the specific language governing rights and limitations under the
# * License.
# *
# * The Original Code is Raindrop.
# *
# * The Initial Developer of the Original Code is
# * Mozilla Messaging, Inc..
# * Portions created by the Initial Developer are Copyright (C) 2009
# * the Initial Developer. All Rights Reserved.
# *
# * Contributor(s):
# *

# This is the 'oauth' API implementation.  Note many globals come
# via (and this script must be run via) raindrop-apirunner.py.

import time

from raindrop.proto import xoauth

class ConsumerAPI(API):
    def _get_consumer(self):
        # TODO: pull these from the .raindrop file, the oauth consumer key,
        # and oauth consumer secret.
        return xoauth.OAuthEntity('anonymous', 'anonymous')

    def _get_url_generator(self, args):
        # TODO: figure out if we need to pass a real username here
        if args['provider'] == 'gmail':
            return xoauth.GoogleAccountsUrlGenerator('username')
        #TODO: provider=twitter?
        raise APIErrorResponse(400, "unknown oauth provider")

    def request(self, req):
        self.requires_get(req)
        db = RDCouchDB(req)

        args = self.get_args(req, 'provider', _json=False)

        if args['provider'] == 'gmail':
            scope = 'https://mail.google.com/'
        else:
            #TODO: provider=twitter?
            raise APIErrorResponse(400, "unknown oauth provider")
        url_gen = self._get_url_generator(args)

        consumer = self._get_consumer()
        callback_url = self.absuri(db, '_api/oauth/consumer/request_done?provider=' + args['provider'])

        # Note the xoauth module automatically generates nonces and timestampts to prevent replays.)
        request_entity = xoauth.GenerateRequestToken(consumer, scope, None, None,
                                           callback_url, url_gen)

        # TODO: Save the request secret in the ~/.raindrop file? We still need
        # to finalize the 'workflow' before we can finalize the best place
        # though (eg, we can't save under an account in ~/.raindrop before
        # that account has been created!)

        url = '%s?oauth_token=%s' % (url_gen.GetAuthorizeTokenUrl(),
                                     xoauth.UrlEscape(request_entity.key))
        return [None, 302, { 'Location': url, 'Set-Cookie': 'oauth=%s' % xoauth.UrlEscape(request_entity.secret)}]

    def request_done(self, req):
        self.requires_get(req)
        db = RDCouchDB(req)
        oauth_token = req['query']['oauth_token']
        oauth_verifier = req['query']['oauth_verifier']
        args = self.get_args(req, 'provider', oauth_verifier=None, oauth_token=None, _json=False)

        # Read the request secret from the cookie
        # TODO: reconsider this, ideally store it serverside
        oauth_secret = xoauth.UrlUnescape(req['cookie']['oauth'])
        if oauth_secret:
            request_token = xoauth.OAuthEntity(oauth_token, oauth_secret)
            log("REQ token=%r, secret=%r", oauth_token, oauth_secret)
    
            # Make the oauth call to get the final verified token
            verified_token = xoauth.GetAccessToken(self._get_consumer(), request_token, oauth_verifier,
                                            self._get_url_generator(args))
    
            # TODO: save this token in the .raindrop file.
    
            # Send the redirect to the user to finish account setup.
            # TODO: generate the right return URL. Maybe an input to the consumer/request
            # function?
            fragment = "oauth_success_" + args['provider']
        else:
            fragment = "oauth_failure_" + args['provider']

        url = self.absuri(db, 'signup/index.html#' + fragment)

        return [None, 302, { 'Location': url, 'Set-Cookie': 'oauth='}]

# A mapping of the 'classes' we expose.  Each value is a class instance, and
# all 'public' methods (ie, those without leading underscores) on the instance
# are able to be called.
dispatch = {
    '_raw_methods': {
        'request': True,
        'request_done': True
    },
    'consumer': ConsumerAPI(),
}

# The standard raindrop extension entry-point (which is responsible for
# exposing the REST API end-point) - so many points!
def handler(request):
    return api_handle(request, dispatch)
