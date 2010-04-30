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

require.def("rdw/Folder",
["rd", "dojo", "rdw/GenericGroup"],
function (rd, dojo, GenericGroup) {

    return dojo.declare("rdw/Folder", [GenericGroup], {
        /**
         * The relative importance of this group widget. 0 is most important.
         */
        groupSort: 10,

        extraClass: "rdwFolder",

        /**
         * Determines if the widget can support this summary.
         *
         * @param summary {object} the group summary API object
         */
        canHandleGroup: function (summary) {
            return summary.rd_key[0] === "folder";
        },

        postCreate: function () {
            this.inherited("postCreate", arguments);

            this.connect(this.nameNode, "onclick", "onNameClick");
            this.nameInputNode = dojo.place('<input type="text" class="nameInput boxFlex">', this.nameNode, "after");
            this.nameInputNode.style.display = "none";
            this.connect(this.nameInputNode, "onkeypress", "onNameInputKeyPress");
        },

        /**
         * Handles clicks on the name to edit the title. Should only occur
         * if we are in edit mode.
         * @param {Event} evt
         */
        onNameClick: function (evt) {
            //See if we are in edit mode by looking for an ancestor with
            //bulkEdit class
            if (dojo.query(this.domNode).parents(".bulkEdit").length) {
                this.showNameInput();
            }
        },

        /**
         * If user presses Enter or ESC then close out the editing of the title.
         * @param {Event} evt
         */
        onNameInputKeyPress: function (evt) {
            var key = evt.charOrCode;
            if (key === dojo.keys.ENTER) {
                this.nameNode.firstChild.nodeValue = this.nameInputNode.value;
                this.hideNameInput();
                dojo.stopEvent(evt);
            } else if (key === dojo.keys.ESCAPE) {
                this.hideNameInput();
                dojo.stopEvent(evt);
            }
        },

        showNameInput: function () {
            this.nameInputNode.value = this.nameNode.firstChild.nodeValue;
            this.nameInputNode.style.display = "block";
            this.nameNode.style.display = "none";
            this.nameInputNode.select();
        },

        hideNameInput: function () {
            this.nameInputNode.style.display = "none";
            this.nameNode.style.display = "";
        }
    });
});
