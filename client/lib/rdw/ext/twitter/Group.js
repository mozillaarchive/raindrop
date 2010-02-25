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

require.def("rdw/ext/twitter/Group",
["rd", "dojo", "rdw/GenericGroup", "rdw/Message"],
function (rd, dojo, GenericGroup) {

    /**
     * Groups twitter broadcast messages into one "conversation"
     */
    return dojo.declare("rdw.ext.twitter.Group", [GenericGroup], {
        /**
         * The relative importance of this group widget. 0 is most important.
         */
        groupSort: 1,

        /** Extra classes to add to the top level node */
        extraClass: "rdwExtTwitterGroup rdwExtAccountGroup",

        /** Module used to display messages */
        messageCtorName: "rdw/Message",

        /**
         * Djit lifecycle method, before template is created/injected in the DOM.
         */
        postMixInProperties: function () {
            this.inherited("postMixInProperties", arguments);
            this.title = "Twitter";
            this.groupHref = "#rd:twitter";
        },

        /**
         * Djit lifecycle method, after template is injected in the DOM.
         */
        postCreate: function () {
            this.inherited("postCreate", arguments);
            this.subscribe("rd/onHashChange", "onHashChange");
        },

        /**
         * Determines if the widget can support this summary.
         *
         * @param summary {object} the group summary API object
         */
        canHandleGroup: function (summary) {
            var key = summary.rd_key;
            return key[0] === "display-group" && key[1] === "twitter";
        },

        /**
         * Handles hash changes. If the hash change matches this group, set a style
         * on this group. Otherwise, unset a style on it.
         * 
         * @param {String} value
         */
        onHashChange: function(value) {
            dojo[(value === "rd:twitter" ? "addClass" : "removeClass")](this.domNode, "inflowSelected");
        }
    });
});
