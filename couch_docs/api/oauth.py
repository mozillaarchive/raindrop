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
    def _get_consumer(self, oauth_config):
        # TODO: pull these from the .raindrop file, the oauth consumer key,
        # and oauth consumer secret.
        return xoauth.OAuthEntity(oauth_config['consumer_key'], oauth_config['consumer_secret'])

    # gets the provider from request args, and makes sure provider is valid,
    # otherwise raises an exception. Use this method in top level API entry
    # points to validate provider.
    def _get_provider_name(self, args):
        provider = args['provider']
        if provider != 'gmail' and provider != 'twitter':
            raise APIErrorResponse(400, "unknown oauth provider")
        return provider

    def _get_url_generator(self, provider, username):
        # TODO: figure out if we need to pass a real username here
        if provider == 'gmail':
            return xoauth.GoogleAccountsUrlGenerator(username or 'username')
        elif provider == 'twitter':
            return xoauth.TwitterAccountsUrlGenerator()

    def request(self, req):
        self.requires_get(req)
        log("1");
        db = RDCouchDB(req)
        log("2");
        config = get_api_config(req)
        log("3");
        args = self.get_args(req, 'provider', 'username', addresses=None, _json=False)
        log("4");
        provider = self._get_provider_name(args)
        log("5");
        provider_config = config.oauth[provider]
        username = args['username']
        log("6");

        if provider == 'gmail':
            scope = 'https://mail.google.com/'
            if username.find('@') == -1:
                username += '@gmail.com'
        elif provider == 'twitter':
            scope = 'http://twitter.com/'
        log("7");

        url_gen = self._get_url_generator(provider, username)
        log("8");

        consumer = self._get_consumer(provider_config)
        log("9");

        callback_url = self.absuri(db, '_api/oauth/consumer/request_done?provider=' + args['provider'])
        log("10");

        # Note the xoauth module automatically generates nonces and timestamps to prevent replays.)
        request_entity = xoauth.GenerateRequestToken(consumer, scope, None, None,
                                           callback_url, url_gen)
        log("11");

        # Save the request secret in the ~/.raindrop file
        provider_config['request_key'] = request_entity.key
        provider_config['request_secret'] = request_entity.secret
        #TODO: make sure username, if gmail, ends with a @gmail if not prefix provided
        provider_config['username'] = username
        provider_config['addresses'] = args['addresses']

        log("12");

        config.save_oauth(config.OAUTH_PREFIX + provider, provider_config)
        log("13");

        url = '%s?oauth_token=%s' % (url_gen.GetAuthorizeTokenUrl(),
                                     xoauth.UrlEscape(request_entity.key))
        log("redirecting to %r and requesting to land back on %r",
            url, callback_url)
        return [None, 302, { 'Location': url }]

    def request_done(self, req):
        self.requires_get(req)
        db = RDCouchDB(req)
        config = get_api_config(req)
        args = self.get_args(req, 'provider', oauth_verifier=None, oauth_token=None, _json=False)
        provider = self._get_provider_name(args)
        provider_config = config.oauth[provider]
        username = provider_config['username']

        oauth_token = req['query']['oauth_token']
        oauth_verifier = req['query']['oauth_verifier']

        # Read the request secret from .raindrop file
        request_key = provider_config['request_key']
        request_secret = provider_config['request_secret']
        if request_secret and request_key == oauth_token:
            request_token = xoauth.OAuthEntity(oauth_token, request_secret)

            # Make the oauth call to get the final verified token
            verified_token = xoauth.GetAccessToken(self._get_consumer(provider_config), request_token, oauth_verifier,
                                            self._get_url_generator(provider, username))

            # Save this token in the .raindrop file as an account setting
            acct = {
                'oauth_token': verified_token.key,
                'oauth_token_secret': verified_token.secret,
                'oauth_consumer_key': provider_config['consumer_key'],
                'oauth_consumer_secret': provider_config['consumer_secret'],
                'username': username,
            }
            if provider == 'gmail':
                # Need to set up imap and smtp sections
                imap = acct.copy()
                if 'addresses' in provider_config:
                    imap['addresses'] = provider_config['addresses']
                imap['kind'] = 'gmail'
                imap['proto'] = 'imap'
                # with kind=gmail we can avoid settings like 'host', 'ssl', etc
                config.save_account(config.ACCOUNT_PREFIX + 'imap-' + imap['username'], imap)

                smtp = acct.copy()
                smtp['kind'] = 'smtp'
                smtp['proto'] = 'smtp'
                smtp['ssl'] = False
                smtp['host'] = 'smtp.gmail.com'
                smtp['port'] = 587
                config.save_account(config.ACCOUNT_PREFIX + 'smtp-' + smtp['username'], smtp)
            elif provider == 'twitter':
                twitter = acct.copy()
                twitter['kind'] = 'twitter'
                twitter['proto'] = 'twitter'
                config.save_account(config.ACCOUNT_PREFIX + 'twitter-' + twitter['username'], twitter)

            # Remove oauth section
            config.delete_section(config.OAUTH_PREFIX + provider)

            # Send the redirect to the user to finish account setup.
            # TODO: generate the right return URL. Maybe an input to the consumer/request
            # function?
            fragment = "oauth_success_" + provider
        else:
            fragment = "oauth_failure_" + provider

        url = self.absuri(db, 'signup/index.html#' + fragment)

        return [None, 302, { 'Location': url }]

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
