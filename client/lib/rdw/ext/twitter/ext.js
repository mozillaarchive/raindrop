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

//Just a collection of require.modify calls.
require.modify("rdw/Summary", "rdw/ext/twitter/ext-rdw/Summary",
    ["rd", "dojo", "rdw/ext/twitter/Summary", "rdw/Summary"],
    function (rd, dojo, Summary) {
        rd.applyExtension("rdw/ext/twitter/ext", "rdw/Summary", {
            addToPrototype: {
                twitter: function () {
                    var summaryWidget = new Summary({
                    }, dojo.create("div"));

                    this.addSupporting(summaryWidget);
                    summaryWidget.placeAt(this.domNode);
                }
            }
        });
    }
);

require.modify("rdw/SummaryGroup", "rdw/ext/twitter/ext-rdw/SummaryGroup",
    ["rd", "rdw/SummaryGroup"],
    function (rd) {
        rd.applyExtension("rdw/ext/twitter/ext", "rdw/SummaryGroup", {
            addToPrototype: {
                topics: {
                    "rd-protocol-twitter": "twitter"
                },

                twitter: function () {
                    this.domNode.innerHTML = "";
                }
            }
        });
    }
);

require.modify("rdw/Conversations", "rdw/ext/twitter/ext-rdw/Conversations",
    ["rd", "dojo", "rd/api", "rdw/Conversations", "rdw/ext/twitter/Conversation"],
    function (rd, dojo, api) {
        rd.applyExtension("rdw/ext/twitter/ext", "rdw/Conversations", {
            after: {
                postCreate: function () {
                    //Bind an onTweet handler so new tweets can be inserted
                    //into the flow.
                    this.connect(this.domNode, "ontweet", "onTweet");
                }
            },

            addToPrototype: {
                convoModules: [
                    "rdw/ext/twitter/Conversation"
                ],
    
                fullConvoModules: [
                    "rdw/ext/twitter/Conversation"
                ],
    
                topics: {
                    "rd-protocol-twitter": "twitter"
                },

                topicConversationCtorNames: {
                    "rd-protocol-twitter": "rdw/ext/twitter/Conversation"
                },

                /** Responds to requests to show all twitter messages */
                twitter: function (callType) {
                    api({
                        url: 'inflow/conversations/in_groups',
                        limit: this.conversationLimit,
                        message_limit: this.messageLimit,
                        keys: [
                            ["display-group", "twitter"]
                        ],
                        skip: this.skipCount
                    })
                    .ok(dojo.hitch(this, function (conversations) {
                        this.updateConversations(callType, "summary", conversations); 
                        //Only set up summary widget if this is a fresh call
                        //to the twitter timeline.
                        if (!callType && this.summaryWidget.twitter) {
                            this.summaryWidget.twitter();
                        }
                    }));
                },

                onTweet: function (evt) {
                    //Called when the twitter compose has tweeted a new
                    //message. Insert it at the top of the conversations.
                    var msg = evt.tweet,
                        body = msg.schemas["rd.msg.body"],

                        //Construct a fake conversation.
                        convo = {
                            from_display: body.from_display,
                            id: msg.id,
                            identities: [body.from],
                            message_ids: [msg.id],
                            messages: [msg],
                            subject: null,
                            unread_ids: [msg.id]
                        },

                        widget = this.createConvoWidget(convo, this.listNode, "first");

                    //Animate showing it. Use a setTimeout so the DOM
                    //can update to show the empty space and make anim smoother.
                    dojo.style(widget.domNode, "opacity", 0);
                    setTimeout(function() {
                        dojo.fadeIn({
                            node: widget.domNode,
                            duration: 700
                        }).play();
                    }, 15);

                    dojo.stopEvent(evt);
                }
            }
        });
    }
);

require.modify("rdw/Widgets", "rdw/ext/twitter/ext-rdw/Widgets",
    ["rd", "dijit", "rdw/Widgets", "rdw/ext/twitter/Group"],
    function (rd, dijit) {
        rd.applyExtension("rdw/ext/twitter/ext", "rdw/Widgets", {
            addToPrototype: {
                summaryModules: [
                    "rdw/ext/twitter/Group"
                ]
            }
        });
    }
);

