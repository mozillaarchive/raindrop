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

/*jslint nomen: false */
/*global require: false */
"use strict";

require.def("rdw/conversation/GenericGroup",
["rd", "dojo", "dojo/string", "rdw/_Base", "rdw/fx/wiper",
 "rdw/conversation/GenericGroupMessage",
 "text!rdw/conversation/templates/GenericGroup!html"],
function (rd, dojo, string, Base, wiper, GenericGroupMessage, template) {
    /**
     * Groups some broadcast/general group messages into one "conversation"
     */
    return dojo.declare("rdw.conversation.GenericGroup", [Base, wiper], {
        templateString: template,

        /**
         * Widget lifecycle method, before template is created.
         */
        postMixInProperties: function () {
            this.inherited("postMixInProperties", arguments);
            if (!this.summary.title) {
                this.summary.title = "Unknown";
            }
        },

        /**
         * Widget lifecycle method, called after template is in the DOM.
         */
        postCreate: function () {
            this.inherited("postCreate", arguments);
            this.wiperInit("closed");
        },

        /**
         * Determines if the widget can support this summary. Subclasses should
         * override this method.
         *
         * @param summary {object} the group summary API object
         */
        canHandleGroup: function (summary) {
            return true;
        }
    });
});
