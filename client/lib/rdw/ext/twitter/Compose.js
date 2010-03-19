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

require.def("rdw/ext/twitter/Compose",
        ["require", "rd", "dojo", "rdw/_Base", "rd/accountIds", "dojo/io/script",
         "rdw/ext/twitter/api", "rdw/placeholder", "rdw/QuickCompose", "text!rdw/ext/twitter/Compose!html"],
function (require,   rd,   dojo,   Base,        accountIds,      script,
          twitterApi,            placeholder,      QuickCompose,       template) {

    var Compose = dojo.declare("rdw.ext.twitter.Compose", [Base], {

        /** the ID to use for the twitter API call when replies are used. */
        inReplyTo: null,

        /**
         * The name to use to start a reply, as in @inReplyToName. Only used
         * if inReplyTo is set.
         */
        inReplyToName: null,

        /**
         * Text to populate the input area.
         */
        tweetText: "",

        templateString: template,

        blankImgUrl: require.nameToUrl("rdw/resources/blank", ".png"),

        /** Dijit lifecycle method before template generation. */
        postMixInProperties: function () {
            this.inherited("postMixInProperties", arguments);

            if (this.inReplyTo) {
                this.buttonName = this.i18n.reply;
            } else {
                //TODO: create an i18n bundler for twitter extension.
                this.buttonName = "tweet";
            }
            
            if (!this.tweetText && this.inReplyTo && this.inReplyToName) {
                this.tweetText = "@" + this.inReplyToName + " ";
            }
        },

        /** Dijit lifecycle method after template insertion in the DOM. */
        postCreate: function () {
            this.inherited("postCreate", arguments);

            //Find twitter name in the accounts.
            var name, i, id;
            for (i = 0; (id = accountIds[i]); i++) {
                if (id[0] === "twitter") {
                    this.twitterId = id;
                    name = id[1];
                    break;
                }
            }

            //Fetch image from twitter, or used cached value
            if (Compose.profileImageUrl) {
                this.setProfileImage();
            } else {
                script.get({
                    url: 'http://api.twitter.com/1/users/show/' + name + '.json',
                    jsonp: "callback",
                    load: dojo.hitch(this, function (data) {
                        Compose.profileImageUrl = data.profile_image_url;
                        this.setProfileImage();
                    })
                });
            }

            //Set up placeholder behavior for textarea.
            placeholder(this.domNode);
        },

        setProfileImage: function () {
            this.imgNode.src = Compose.profileImageUrl;
        },

        /**
         * Utility method for focusing in the text area, for use by
         * outside callers.
         */
        focus: function() {
            this.textAreaNode.focus();
        },

        /**
         * Handles form submits, makes sure text is not too long.
         */
        onSubmit: function (evt) {
            var body = dojo.trim(this.textAreaNode.value);
            this.errorNode.innerHTML = "";

            //Only send if there is a message less than 140 and only
            //if the textarea is not in "placeholder text" mode.
            if (body && body.length < 140 && !dojo.hasClass(this.textAreaNode, "placeholder")) {
                twitterApi.send(this.twitterId, body, this.inReplyTo)
                .ok(this, function () {
                    //TODO do more here, put the tweet in the flow?
                    //How to get it to conform to data structure?
                    this.textAreaNode.value = "";
                    this.inReplyTo = null;
                })
                .error(this, function (err) {
                    rd.escapeHtml(err + "", this.errorNode, "only");
                });
            }

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

    return Compose;
});
