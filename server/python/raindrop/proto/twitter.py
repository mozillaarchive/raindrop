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

'''
Fetch twitter raw* objects
'''

# prevent 'import twitter' finding this module!
from __future__ import absolute_import
from __future__ import with_statement

import logging
import sys
import re
import twisted.python.log
from twisted.internet import defer, threads

from ..proc import base

# See http://code.google.com/p/python-twitter/issues/detail?id=13 for info
# about getting twisted support into the twitter package.
# Sadly, the twisty-twitter package has issues of its own (like calling
# delegates outside the deferred mechanism meaning you can't rely on callbacks
# being completed when they say they are.)

# So for now we are going with the blocking twitter package used via
# deferToThread for all blocking operations...
import twitter
import calendar, rfc822

logger = logging.getLogger(__name__)

re_user = re.compile(r'@(\w+)')

def user_to_raw(user):
    return dict([('twitter_'+name.lower(), unicode(val).encode('utf-8')) \
      for name, val in user.iteritems() if val is not None])

# Used for direct messages and regular tweets
def tweet_to_raw(tweet):
    ret = {}
    # get the tweet user or the dm sender, this will error if no user, or sender
    # but that shouldn't happen to us... right?
    user = tweet.pop("user", None) or tweet.pop("sender")

    # simple hacks - users just become the screenname.
    # XXX This needs to be fixed as the screen_name can change but the id will
    # remain constant
    ret["twitter_user"] = user.get("screen_name")
    ret["twitter_user_name"] = user.get("name")

    # XXX It'd be better to keep this function in tweet-to-common but we make calls
    # for raw tweets via the this field in the API
    # fake a timestamp value we need for comparing
    ret['twitter_created_at_in_seconds'] = \
      calendar.timegm(rfc822.parsedate(tweet.get("created_at")))

    ret.update(dict([('twitter_'+name.lower(), unicode(val).encode('utf-8')) \
      for name, val in tweet.iteritems() if val is not None]))

    return ret

class TwitterProcessor(object):
    # The 'id' of this extension
    # XXX - should be managed by our caller once these 'protocols' become
    # regular extensions.
    rd_extension_id = 'proto.twitter'
    def __init__(self, account, conductor, options):
        self.account = account
        self.options = options
        self.doc_model = account.doc_model # this is a little confused...
        self.conductor = conductor
        self.twit = None
        self.seen_tweets = None

    def attach(self):
        logger.info("attaching to twitter...")
        username = self.account.details['username']
        pw = self.account.details['password']
        return threads.deferToThread(twitter.api.Twitter,
                                     email=username, password=pw
                                     ).addCallback(self.attached)


    @defer.inlineCallbacks
    def attached(self, twit):
        logger.info("attached to twitter - fetching timeline")
        self.twit = twit

        # Lets get fancy and check our rate limit status on twitter

        # The supplied dictionary looks like this
        # rate_limit_status {
            # reset_time :              Tue Feb 23 04:22:53 +0000 2010
            # remaining_hits :          127
            # hourly_limit :            150
            # reset_time_in_seconds :   1266898973
        # }
        rate_limit_status = twit.account.rate_limit_status()
        logger.info("rate limit status: %s more hits, resets at %s",
                    rate_limit_status.get("remaining_hits"),
                    rate_limit_status.get("reset_time"))

        # Throw a warning in the logs if this user is getting close to the rate
        # limit.  Hopefully we can look for these to tune how often we should be
        # checking in with Twitter
        if rate_limit_status.get("remaining_hits", 0) < 30:
            logger.warn("Twitter is nearing the rate limit and will reset at %s",
                         rate_limit_status.reset_time)

        # If we aren't going to have enough calls lets just fail out and quit
        if rate_limit_status.get("remaining_hits", 0) < 2:
            logger.error("Your Twitter has hit the rate limit and will reset at %s",
                         rate_limit_status.reset_time)
            return

        # XXX We grab this and don't use it, but it's fun to get anyway
        me = None

        this_users = {} # probably lots of dupes
        this_items = {} # tuple of (twitter_item, rd_key, schema_id)
        keys = []

        # We could use the since_id to limit the traffic between us and Twitter
        # however it might not be worth the extra call to our systems 
        since_id = 1
        startkey = ["rd.msg.tweet.raw", "twitter_id"]
        endkey = ["rd.msg.tweet.raw", "twitter_id", 999999999999]
        results = yield self.doc_model.open_view(startkey=startkey, endkey=endkey,
                                                 limit=1, reduce=False,
                                                 descending=True,
                                                 include_docs=False)
        # We grab the since_id but don't use it yet until we've got some unit
        # tests to show that this works correctly every time
        if len(results.get("rows")) > 0:
            logger.info("results %s", results.get("rows")[0].get("value").get("rd_key")[1])
            since_id = int(results.get("rows")[0].get("value").get("rd_key")[1])

        # statuses.home_timeline gets us our friends latest tweets (+retweets)
        # as well as their identity info all in a single request
        # This doesn't get us all of our friends but with 200 tweets we'll at
        # least get your most chatty friends
        tl= yield threads.deferToThread(self.twit.statuses.home_timeline,
                                        count=200)
        for status in tl:
            id = int(status.get("id"))
            rd_key = ['tweet', id]
            schema_id = 'rd.msg.tweet.raw'
            keys.append(['rd.core.content', 'key-schema_id', [rd_key, schema_id]])
            this_items[id] = (status, rd_key, schema_id)
            this_users[status.get("user").get("screen_name")] = status.get("user")
            if status.get("retweeted_status", None) is not None:
                logger.info("Twitter status id: %s is a retweet", id)

        # Grab any direct messages that are waiting for us
        ml = yield threads.deferToThread(self.twit.direct_messages)
        for dm in ml:
            id = int(dm.get("id"))
            rd_key = ['tweet-direct', id]
            schema_id = 'rd.msg.tweet-direct.raw'
            keys.append(['rd.core.content', 'key-schema_id', [rd_key, schema_id]])
            this_items[id] = (dm, rd_key, schema_id)
            # sender gives us an entire user dictionary for the sender so lets
            # save that for later
            if dm.get("sender_screen_name") not in this_users:
                this_users[dm.get("sender_screen_name")] = dm.get("sender")

            # this is a trick way to get our own twitter account information
            # and pop removes the duplicate data from the dm
            me = dm.pop("twitter_recipient", None)

        # execute a view to work out which of these tweets/messages are new
        # if we were using the since_id correctly this probably wouldn't be a
        # necessary step
        results = yield self.doc_model.open_view(keys=keys, reduce=False)
        seen_tweets = set()
        for row in results['rows']:
            seen_tweets.add(row['value']['rd_key'][1])

        infos = []
        for tid in set(this_items.keys())-set(seen_tweets):
            # create the schema for the tweet/message itself.
            item, rd_key, schema_id = this_items[tid]
            fields = tweet_to_raw(item)
            infos.append({'rd_key' : rd_key,
                          'rd_ext_id': self.rd_extension_id,
                          'rd_schema_id': schema_id,
                          'items': fields})

        # now the same treatment for the users we found; although for users
        # the fact they exist isn't enough - we also check their profile is
        # accurate.
        keys = []
        for sn in this_users.iterkeys():
            keys.append(['rd.core.content', 'key-schema_id',
                         [["identity", ["twitter", sn]], 'rd.identity.twitter']])
        # execute a view process these users.
        results = yield self.doc_model.open_view(keys=keys, reduce=False,
                                                 include_docs=True)
        seen_users = {}
        for row in results['rows']:
            _, idid = row['value']['rd_key']
            _, name = idid
            seen_users[name] = row['doc']

        # XXX - check the account user is in the list!!

        # XXX - check fields later - for now just check they don't exist.
        for sn in set(this_users.keys())-set(seen_users.keys()):
            user = this_users[sn]
            if user is None:
                # this probably shouldn't happen anymore
                logger.info("Have unknown user %r - todo - fetch me!", sn)
                continue
            items = user_to_raw(user)
            rdkey = ['identity', ['twitter', sn]]
            infos.append({'rd_key' : rdkey,
                          'rd_ext_id': self.rd_extension_id,
                          'rd_schema_id': 'rd.identity.twitter',
                          'items': items})

        if infos:
            _ = yield self.conductor.provide_schema_items(infos)


class TwitterAccount(base.AccountBase):
    rd_outgoing_schemas = ['rd.msg.outgoing.tweet']

    @defer.inlineCallbacks
    def startSend(self, conductor, src_doc, dest_doc):
        logger.info("Sending tweet from TwitterAccount...")

        username = self.details['username']
        pw = self.details['password']
        self.src_doc = src_doc
        _ = yield threads.deferToThread(twitter.api.Twitter,
                                     email=username, password=pw
                                     ).addCallback(self.attached)

    @defer.inlineCallbacks
    def attached(self, twitter_api):
        logger.info("attached to twitter - sending tweet")

        _ = yield self._update_sent_state(self.src_doc, 'sending')

        in_reply_to = None
        if (in_reply_to in self.src_doc):
            in_reply_to = self.src_doc['in_reply_to']

        # Do the actual twitter send.
        try:
            status = yield threads.deferToThread(twitter_api.statuses.update,
                                   status=self.src_doc['body'], in_reply_to_status_id=in_reply_to, source='Raindrop')

            # If status has an ID, then it saved. Otherwise,
            # assume an error
            if ("id" in status):
                # Success
                _ = yield self._update_sent_state(self.src_doc, 'sent')
            else:
                # Log error
                logger.error("Twitter API status update failed: %s", status)
                _ = yield self._update_sent_state(self.src_doc, 'error',
                                              'Twitter API status update failed', status,
                                              # reset to 'outgoing' if temp error.
                                              # or set to 'error' if permanent.
                                              outgoing_state='error')

        except Exception, e:
            logger.error("Twitter API status update failed: %s", str(e))
            _ = yield self._update_sent_state(self.src_doc, 'error',
                                          'Twitter API failed', str(e),
                                          # reset to 'outgoing' if temp error.
                                          # or set to 'error' if permanent.
                                          outgoing_state='error')

    def startSync(self, conductor, options):
        return TwitterProcessor(self, conductor, options).attach()

    def get_identities(self):
        return [('twitter', self.details['username'])]
