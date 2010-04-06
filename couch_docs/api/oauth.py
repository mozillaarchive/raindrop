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
    def get_consumer(self):
        # TODO: pull these from the .raindrop file, the oauth consumer key,
        # and oauth consumer secret.
        return xoauth.OAuthEntity('anonymous', 'anonymous')

    def get_url_generator(self):
        # TODO: figure out if we need to pass a real username here
        return xoauth.GoogleAccountsUrlGenerator('username')

    def request(self, req):
        self.requires_get(req)

        #TODO: take a provider=gmail or provider=twitter and to the right branching

        consumer = self.get_consumer()

        # TODO: generate this full URL appropriately
        callback_url = 'http://127.0.0.1/raindrop/_api/oauth/consumer/request_done'

        request_entity = xoauth.GenerateRequestToken(consumer, 'https://mail.google.com/', None, None,                                            
                                           callback_url,
                                           self.get_url_generator())

        # Save the request secret in the
        # TODO use nonces to prevent replays.
        oauth_requests[request_entity.key] = request_entity.secret

        url = '%s?oauth_token=%s' % (xoauth.GoogleAccountsUrlGenerator('username').GetAuthorizeTokenUrl(),
                                     xoauth.UrlEscape(request_entity.key))

        return [None, 302, { 'Location': url, 'Set-Cookie': 'oauth=%s' % xoauth.UrlEscape(request_entity.secret)}]

    def request_done(self, req):
        self.requires_get(req)
        oauth_token = req['query']['oauth_token']
        oauth_verifier = req['query']['oauth_verifier']

        # Read the request secret from the cookie
        # TODO: reconsider this, ideally store it serverside
        oauth_secret = xoauth.UrlUnescape(req['cookie']['oauth'])

        request_token = xoauth.OAuthEntity(oauth_token, oauth_secret)

        # Make sure the token matches a request token we were waiting for
        # TODO: this is not persistent
        #if not request_token in oauth_requests:
        #    raise APIErrorResponse(400, "unknown OAUTH request")

        # Remove the token from oauth_requests
        # TODO
        # del oauth_requests[request_token]

        # Make the oauth call to get the final verified token
        verified_token = xoauth.GetAccessToken(self.get_consumer(), request_token, oauth_verifier,
                                        self.get_url_generator())

        # TODO: save this token in the .raindrop file.

        # Send the redirect to the user to finish account setup.
        # TODO: generate the right return URL. Maybe an input to the consumer/request
        # function?
        # TODO: DO NOT return the token here, just done for testing
        url = 'http://127.0.0.1/raindrop/signup/index.html#%s' % (verified_token.key)

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

# In memory store of oauth tokens/secrets
# TODO: make this more robust for the future.
# TODO: this is not persistent
oauth_requests = {}

# The standard raindrop extension entry-point (which is responsible for
# exposing the REST API end-point) - so many points!
def handler(request):
    return api_handle(request, dispatch)
