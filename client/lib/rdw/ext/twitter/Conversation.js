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
/*global require: false, alert: false */
"use strict";

require.def("rdw/ext/twitter/Conversation",
["require", "rd", "dojo", "dijit", "rd/api", "rdw/ext/twitter/api", "rdw/Conversation", "rdw/ext/twitter/Message",
 "rd/friendly",
 "text!rdw/ext/twitter/Conversation!html",
 "text!rdw/ext/twitter/retweet!html",
 "text!rdw/ext/twitter/retweetDone!html",
 "rdw/ext/twitter/Compose"],
function (require, rd, dojo, dijit, api, tapi, Conversation, Message, friendly,
          template, retweetTemplate, retweetDoneTemplate) {

    /**
     * Groups twitter broadcast messages into one "conversation"
     */
    var TwitterConversation = dojo.declare("rdw.ext.twitter.Conversation", [Conversation], {
        //The name of the constructor function (module) that should be used
        //to show individual messages.
        messageCtorName: "rdw/ext/twitter/Message",

        /**
         * Name of widget to use for replies.
         */
        replyCtorName: "rdw/ext/twitter/Compose",

        templateString: template,

        /**
         * Determines if the widget can support this conversation.
         *
         * @param conversation {object} the conversation API object.
         */
        canHandle: function (conversation) {
            var msg = conversation.messages[0];
            return !this.conversation && conversation.message_ids[0][0] === "tweet";
        },

        /** Widget lifecycle method. */
        destroy: function () {
            if (this.twitterReplyWidget) {
                delete this.twitterReplyWidget;
            }
        },

        /**
         * Shows twitter reply area if not already visible.
         */
        toggleReply: function (evt, skipAnim) {
            if (dojo.hasClass(this.replyNode, "active")) {
                if (skipAnim) {
                    this.resetReply();
                } else {
                    dojo.fadeOut({
                        node: this.twitterReplyWidget.domNode,
                        duration: 700,
                        onEnd: dojo.hitch(this, "resetReply")
                    }).play();
                }
            } else {
                if (!this.twitterReplyWidget) {
                    //Get the reply text and inReplyTo value.
                    var msg = this.conversation.messages[this.conversation.messages.length - 1],
                        replyName = msg.schemas["rd.msg.body"].from[1],
                        inReplyTo = msg.id[1];

                    this.twitterReplyWidget = new (require(this.replyCtorName))({
                        inReplyTo: inReplyTo,
                        inReplyToName: replyName
                    }, dojo.create("div"));
                    dojo.style(this.twitterReplyWidget.domNode, "opacity", 0);
                    this.twitterReplyWidget.placeAt(this.domNode);
                }

                this.twitterReplyWidget.domNode.style.display = "";
                dojo.fadeIn({
                    node: this.twitterReplyWidget.domNode,
                    duration: 700,
                    onEnd: dojo.hitch(this, function () {
                        this.twitterReplyWidget.focus();
                    })
                }).play();

                //Set state of reply button
                dojo.addClass(this.replyNode, "active");
                this.replyNode.innerHTML = this.i18n.closeIcon;
            }
        },

        /**
         * Resets display after hiding the reply.
         */
        resetReply: function () {
            dojo.removeClass(this.replyNode, "active");
            this.replyNode.innerHTML = this.i18n.reply;
            this.twitterReplyWidget.domNode.style.display = "none"; 
        },

        /**
         * Handles clicks to the send/close button for reply. If the text
         * of the field is empty or just the @username, then it is a close
         * action
         */
        onTweet: function (evt) {
            var msg = evt.tweet;

            //Show the message in the widget
            this.msgs.push(msg);
            this.addMessage(this.msgs.length - 1, msg);

            //Clean up reply widget and stop the event from going higher.
            this.toggleReply({}, true);
            dojo.stopEvent(evt);
        },

        /**
         * When retweet buttons are clicked, show a confirm before doing the work
         */
        onRetweetClick: function (evt) {
            this.retweetButtonNode = evt.target;
            dijit.showTooltip(rd.template(retweetTemplate, this), this.retweetButtonNode, ["below"]);
        },

        /**
         * Does the actual retweet. It chooses the *first* message in the
         * conversation and retweets that one.
         */
        retweet: function (evt) {
            console.log("retweeted!");
            var tweetId = this.conversation.messages[0].id[1];
            tapi.retweet(tweetId).ok(this, function () {
                dojo.place(rd.template(retweetDoneTemplate, {
                    time: friendly.date(new Date()).friendly
                }), this.domNode);
                dojo.addClass(this.domNode, "retweet");
            });

            this.onRetweetClose(evt);
        },

        /**
         * Closes the retweet confirmation tooltip
         */
        onRetweetClose: function (evt) {
            dijit.hideTooltip(this.retweetButtonNode);
        }
    });

    return TwitterConversation;
});
