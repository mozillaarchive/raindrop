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

require.def("rdw/ext/twitter/Summary",
        ["require", "rd", "dojo", "rdw/_Base", "rd/accountIds", "dojo/io/script",
         "rdw/placeholder", "rdw/QuickCompose", "text!rdw/ext/twitter/Summary!html"],
function (require,   rd,   dojo,   Base,        accountIds,      script,
          placeholder,      QuickCompose,       template) {

    rd.addStyle("rdw/ext/twitter/Summary");

    return dojo.declare("rdw.ext.twitter.Summary", [Base], {
        templateString: template,

        blankImgUrl: require.nameToUrl("rdw/resources/blank", ".png"),

        /** Dijit lifecycle method after template insertion in the DOM. */
        postCreate: function () {
            this.inherited("postCreate", arguments);

            //Find twitter name in the accounts.
            var name, i, id;
            for (i = 0; (id = accountIds[i]); i++) {
                if (id[0] === "twitter") {
                    name = id[1];
                    break;
                }
            }

            //Fetch image from twitter.
            script.get({
                url: 'http://api.twitter.com/1/users/show/' + name + '.json',
                jsonp: "callback",
                load: dojo.hitch(this, function (data) {
                    this.imgNode.src = data.profile_image_url;
                })
            })
            
            //Set up placeholder behavior for textarea.
            placeholder(this.domNode);
        },

        /**
         * Handles form submits, makes sure text is not too long.
         */
        onSubmit: function (evt) {
            dojo.stopEvent(evt);
        },

        twitterLimit: 140,

        /** Check the character count in the textarea. */
        checkCount: function () {
            var count = this.twitterLimit - this.textAreaNode.value.length;
            if (count < 0) {
                dojo.addClass(this.countNode, "error");
                this._isTwitterOver = true;
            } else if (this._isTwitterOver) {
                dojo.removeClass(this.countNode, "error");
                this._isTwitterOver = false;
            }
            this.countNode.innerHTML = count === this.twitterLimit ? "" : count;
        },

        /**
         * Handles clearing of default message
         */
        onFocus: function (evt) {
            
        },

        /**
         * Handles resetting default message if need be
         */
        onBlur: function (evt) {
            
        }
    });
});
