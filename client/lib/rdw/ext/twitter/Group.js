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
["rd", "dojo", "rdw/conversation/GenericGroup", "rdw/fx/wiper"],
function (rd, dojo, GenericGroup, wiper) {

    /**
     * Groups twitter broadcast messages into one "conversation"
     */
    return dojo.declare("rdw.ext.twitter.Group", [GenericGroup, wiper], {
        templateString: '<div class="WidgetBox rdwExtTwitterGroup rdwExtAccountGroup" dojoAttachPoint="headNode">' +
                        '    <div class="WidgetHeader hbox">' +
                        '       <a href="#rd:twitter" dojoAttachPoint="nameNode" class="title start boxFlex">Twitter</a>' +
                        '       <span class="actions">' +
                        '            <button class="wipeToggle" dojoAttachPoint="headNode" dojoAttachEvent="onclick: toggleWiper"></button>' +
                        '       </span>' +
                        '    </div>' +
                        '    <div class="WidgetBody" dojoAttachPoint="bodyNode">' +
                        '        <div class="tweetList" dojoAttachPoint="containerNode"></div>' +
                        '    </div>' +
                        '</div>',

        /**
         * The relative importance of this group widget. 0 is most important.
         */
        groupSort: 1,

        /**
         * Widget lifecycle method, called after template is in the DOM.
         */
        postCreate: function () {
            this.inherited("postCreate", arguments);
            this.wiperInit("closed");
        },

        /**
         * Determines if the widget can support this summary.
         *
         * @param summary {object} the group summary API object
         */
        canHandleGroup: function (summary) {
            var key = summary.rd_key;
            return key[0] === "display-group" && key[1] === "twitter";
        }
    });
});
