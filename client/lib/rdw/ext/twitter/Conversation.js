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
["require", "rd", "dojo", "rd/api", "rdw/Conversation", "rdw/ext/twitter/Message",
 "text!rdw/ext/twitter/Conversation!html", "rdw/ext/twitter/Compose"],
function (require, rd, dojo, api, Conversation, Message, template) {

    /**
     * Groups twitter broadcast messages into one "conversation"
     */
    return dojo.declare("rdw.ext.twitter.Conversation", [Conversation], {
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
        toggleReply: function (evt) {
            if (dojo.hasClass(this.replyNode, "active")) {
                dojo.fadeOut({
                    node: this.twitterReplyWidget.domNode,
                    duration: 700,
                    onEnd: dojo.hitch(this, function (node) {
                        dojo.removeClass(this.replyNode, "active");
                        this.replyNode.innerHTML = this.i18n.reply;
                        node.style.display = "none";
                    })
                }).play();                
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
         * Handles clicks to the send/close button for reply. If the text
         * of the field is empty or just the @username, then it is a close
         * action
         */
        onReplySendClick: function (evt) {
            if (this.replySendNode.innerHTML === this.replySendText) {
                alert("TODO: send reply");
            }

            this.hideReply();
            dojo.stopEvent(evt);
        }
    });
});
