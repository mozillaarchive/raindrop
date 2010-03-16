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

require.def("rdw/ext/twitter/Conversation",
["rd", "dojo", "rdw/Conversation", "rdw/ext/twitter/Message",
 "text!rdw/ext/twitter/Conversation!html", "text!rdw/ext/twitter/quickReply!html"],
function (rd, dojo, Conversation, Message, template, replyTemplate) {

    /**
     * Groups twitter broadcast messages into one "conversation"
     */
    return dojo.declare("rdw.ext.twitter.Conversation", [Conversation], {
        //The name of the constructor function (module) that should be used
        //to show individual messages.
        messageCtorName: "rdw/ext/twitter/Message",

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

        /**
         * Shows twitter reply area if not already visible.
         */
        showReply: function (evt) {
            if (!dojo.hasClass(this.replyNode, "active")) {
                if (!this.quickReplySectionNode) {
                    //Inject the reply section into the DOM, then get the root
                    //element for the reply section.
                    dojo.place(rd.template(replyTemplate, this), this.domNode);
                    this.quickReplySectionNode = dojo.query(".quickReply", this.domNode)[0];

                    //Make sure opacity is set to 0
                    dojo.style(this.quickReplySectionNode, "opacity", 0);

                    //Parse the reply section for dojoAttachEvent/dojoAttachPoint items.
                    this._attachTemplateNodes(this.quickReplySectionNode);
    
                    //Hold on to button values for reply send
                    this.replyCloseText = this.replySendNode.getAttribute("data-close");
                    this.replySendText = this.replySendNode.getAttribute("data-send");
    
                    //Hold on to the name to reply to
                    this.replySenderText = this.conversation.messages[this.conversation.messages.length - 1].schemas["rd.msg.body"].from[1];
                }

                this.quickReplySectionNode.style.display = "";

                //Set reply text
                this.replyTextNode.value = "@" + this.replySenderText;

                dojo.fadeIn({
                    node: this.quickReplySectionNode,
                    duration: 1000
                }).play();
                dojo.addClass(this.replyNode, "active");
            }
            
            dojo.stopEvent(evt);
        },

        hideReply: function () {
            if (dojo.hasClass(this.replyNode, "active")) {
                dojo.fadeOut({
                    node: this.quickReplySectionNode,
                    duration: 1000,
                    onEnd: dojo.hitch(this, function (node) {
                        dojo.removeClass(this.replyNode, "active");
                        node.style.display = "none";
                    })
                }).play();
            }
        },

        /**
         * Handles key ups in the reply area. If the text is just @username
         * or empty, then send button needs to be a close button.
         */
        onReplyKeyUp: function (evt) {
            var text = this.replySendText, value = dojo.trim(this.replyTextNode.value);
            if (!value || value.length <= this.replySenderText.length + 1) {
                text = this.replyCloseText;
            }

            this.replySendNode.innerHTML = text;
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
