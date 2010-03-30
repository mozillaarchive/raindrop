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

/*jslint nomen: false, plusplus: false */
/*global require: false, setTimeout: false */
"use strict";

require.def("rdw/GenericGroup",
["require", "rd", "dojo", "dojo/string", "rd/api", "rdw/_Base", "rdw/fx/wiper",
 "text!rdw/templates/GenericGroup.html",
 "rdw/conversation/Broadcast"],
function (require, rd, dojo, string, api, Base, wiper, template) {
    /**
     * Groups some broadcast/general group messages into one "conversation"
     */
    return dojo.declare("rdw.GenericGroup", [Base, wiper], {
        templateString: template,

        /** How many conversations to show when expanded */
        conversationLimit: 3,

        /** Name of the module to use for displaying a conversation */
        conversationCtorName: "rdw/conversation/Broadcast",

        /**
         * The name of the constructor function (module) that should be used
         * show individual messages.
         * @param {String}
         */
        messageCtorName: null,
  
        /** Optional set of default args to be used when creating instances of
         *  messageCtorName. By default do not want attachments showing.
         *  @param {Object}
         */
        messageCtorArgs: {
            attachmentWidget: null
        },

        /** Extra CSS classes to add to top level DOM node. */
        extraClass: "",

        /** link to use for when clicking on the title. */
        groupHref: "#",

        /**
         * Widget lifecycle method, before template is created.
         */
        postMixInProperties: function () {
            this.inherited("postMixInProperties", arguments);
            this.title = this.summary.title || "Unknown";
        },

        /**
         * Widget lifecycle method, called after template is in the DOM.
         */
        postCreate: function () {
            this.inherited("postCreate", arguments);
            this.wiperInit("closed");

            //If the summary already has its conversations, then set up the
            //state of the widget to have them already rendered.
            var conversations = this.summary.conversations;
            if (conversations && conversations.length) {
                this.renderConvos(conversations);
            }
        },

        /**
         * Determines if the widget can support this summary. Subclasses should
         * override this method.
         *
         * @param summary {object} the group summary API object
         */
        canHandleGroup: function (summary) {
            return true;
        },

        /**
         * Handles clicks to show or hide conversations
         * @param {Event} evt
         */
        onClickToggle: function (evt) {
            this.loadConvos("toggleWiper");
        },

        /**
         * Fetches conversations for this group and displays them.
         * @param {String} [methodName] the name of the method to call on this
         * instance when the conversations are available.
         */
        loadConvos: function (methodName) {
            if (!this.convosAvailable) {
                api({
                    url: 'inflow/conversations/in_groups',
                    keys: [this.summary.rd_key],
                    limit: this.conversationLimit,
                    message_limit: this.messageLimit 
                }).ok(this, function (conversations) {
                    this.renderConvos(conversations, methodName);
                });
            } else {
                if (methodName) {
                    this[methodName]();
                }
            }
        },

        /**
         * Renders the set of conversations., and takes an optional name of
         * a function to call on this instance when done.
         *
         * @param {Array} conversations the conversation API objects.
         * @param {String} [methodName] the method name to call on this object
         * when done.
         */
        renderConvos: function (conversations, methodName) {
            var Ctor = require(this.conversationCtorName),
                i, conversation, widget, args,
                frag = dojo.doc.createDocumentFragment();

            if (conversations && conversations.length) {
                for (i = 0; (conversation = conversations[i]) && (i < this.conversationLimit); i++) {
                    //Construct the args, adding in optional values.
                    args = {
                        conversation: conversation
                    };
                    if (this.messageCtorName) {
                        args.messageCtorName = this.messageCtorName;
                    }
                    if (this.messageCtorArgs) {
                        args.messageCtorArgs = this.messageCtorArgs;
                    }

                    //Make a new widget and track it so it gets cleaned
                    //up correctly.
                    this.addSupporting(new Ctor(args, dojo.create("div", null, frag)));
                }
                this.containerNode.appendChild(frag);
            }

            this.convosAvailable = true;

            if (methodName) {
                //Use a timeout to allow the animation to be smooth,
                //since we just injected some HTML into the DOM.
                setTimeout(dojo.hitch(this, function () {
                    this[methodName]();
                }), 15);
            }
        }
    });
});
