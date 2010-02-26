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

require.def("rdw/GroupRss",
["rd", "dojo", "rdw/GenericGroup"],
function (rd, dojo, GenericGroup) {

    /**
     * Groups twitter broadcast messages into one "conversation"
     */
    return dojo.declare("rdw.Group.Rss", [GenericGroup], {
        /**
         * The relative importance of this group widget. 0 is most important.
         */
        groupSort: 500,

        /** Extra classes to add to the top level node */
        extraClass: "rdwGroupRss",

        /**
         * Determines if the widget can support this summary.
         *
         * @param summary {object} the group summary API object
         */
        canHandleGroup: function (summary) {
            return summary.rd_key[0] === "rss-feed";
        }
    });
});
