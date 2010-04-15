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

require.def("rdw/conversation/BroadcastMulti",
["rd", "dojo", "rdw/_Base", "text!./templates/BroadcastMulti.html"],
function (rd, dojo, Base, template) {

    /**
     * This differs from rdw/conversation/Broadcast in that it does not show
     * a message, but an aggregate display of a conversation that has more
     * than one message.
     */
    return dojo.declare("rdw.conversation.BroadcastMulti", [Base], {
        templateString: template,

        /** Passed in property, the conversation API object */
        conversation: null,

        postMixInProperties: function () {
            this.inherited("postMixInProperties", arguments);

            this.expandLink = "rd:conversation:" + dojo.toJson(this.conversation.id);
            this.subject = rd.escapeHtml(this.conversation.subject || "");
            this.from = rd.escapeHtml(this.conversation.from_display.join(", "));
            this.unread = "";
            if (this.conversation.unread_ids && this.conversation.unread_ids.length) {
                this.unread = rd.template(this.i18n.newCount, {
                    count: this.conversation.unread_ids.length
                });
            }
        }
    });
});
