/* ***** BEGIN LICENSE BLOCK *****
 * Version: MPL 1.1
 *
 * The contents of this file are subject to the Mozilla Public License Version
 * 1.1 (the "License"); you may not use this file except in compliance with
 * the License. You may obtain a copy of the License at
 * http://www.mozilla.org/MPL/
 *
 * Software distributed under the License is distributed on an "AS IS" basis,
 * WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
 * for the specific language governing rights and limitations under the
 * License.
 *
 * The Original Code is Raindrop.
 *
 * The Initial Developer of the Original Code is
 * Mozilla Messaging, Inc..
 * Portions created by the Initial Developer are Copyright (C) 2009
 * the Initial Developer. All Rights Reserved.
 *
 * Contributor(s):
 * */

/*jslint plusplus: false, nomen: false */
/*global require: false */
"use strict";

require.def("rdw/ext/twitter/api",
["rd", "dojo", "rd/api"],
function (rd, dojo, api) {

    var tapi = {
        /**
         * Sends a tweet via the Raindrop backend.
         *
         * @param {Array} from the identity ID of the sender.
         * @param {String} body 140 character-limited body of the tweet.
         * @param {String} inReplyTo, the twitter message ID that this tweet
         * is responding to. Note that the body MUST contain an @username
         * that matches the author of the inReplyTo ID.
         *
         * @returns {dojo.Deferred} use ok() and error() to bind callbacks
         * to success and error states respectively.
         */
        send: function (from, body, inReplyTo) {
            var dfd = new dojo.Deferred();

            //Valid character limit
            if (!body) {
                dfd.errback(new Error("rdw/ext/twitter:missingTweet"));
            } else if (body.length > 140) {
                dfd.errback(new Error("rdw/ext/twitter:tweetTooLong"));
            } else if (inReplyTo && body.indexOf("@") === -1) {
                dfd.errback(new Error("rdw/ext/twitter:replyToMissingUserName"));
            } else {

                api().put({
                    doc: api()._makeOutSchema(["tweet", "out-" + (new Date()).getTime()],
                        "rd.msg.outgoing.tweet", {
                            from: from,
                            body: body,
                            in_reply_to: inReplyTo
                        })
                    })
                .ok(dfd)
                .error(dfd);
            }

            return dfd;
        },

        /**
         * Sends a retweet request to the backend, which will then take it
         * on to twitter.
         * @param {String} retweetId the ID of the tweet that is being retweeted.
         */
        retweet: function (retweetId) {
            var dfd = new dojo.Deferred(), schemaItems = {}, doc;

            api().put({
                doc: api()._makeOutSchema(
                    ["tweet", "out-" + (new Date()).getTime()],
                    "rd.msg.outgoing.tweet", {
                        retweet_id: retweetId
                    })
                })
            .ok(dfd)
            .error(dfd);

            return dfd;
        }
    };
    
    return tapi;
});
