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
/*global require: false, setTimeout: false, clearTimeout: false, console: false,
setInterval: false, clearInterval: false */
"use strict";

require.def("rd/autoSync",
["rd", "dojo"],
function (rd, dojo) {
    var autoSync = {
        /** The path to the sync document with last sync timestamp */
        url: rd.dbPath + "rc!raindrop.InN5bmMtc3RhdHVzIg==!rd.core.sync-status",

        /** How often to check, in milliseconds */
        interval: 15000,

        /** Stores the timestamp in the sync document */
        timestamp: 0,

        /**
         * Does the fetch of the sync document and triggers the next sync
         * check.
         */
        fetch: function () {
            //Be sure to clean up any outstanding timeout, and cancel
            //any previous fetch call.
            if (this.timeoutId) {
                clearTimeout(this.timeoutId);
            }
            if (this.deferred) {
                this.deferred.cancel();
                this.deferred = null;
            }

            this.deferred = dojo.xhr("GET", {
                url: this.url,
                handleAs: "json",
                load: dojo.hitch(this, "_done"),
                error: dojo.hitch(this, "_error")
            });
        },

       /**
         * Callback from XHR call for getting the sync document.
         * @param {Object} doc the sync document from the couch.
         */
        _done: function (doc) {
            var lastTimestamp = this.timestamp;
            this.timestamp = doc.timestamp;

            //Use a setTimeout to allow the timestamp above to be dynamically
            //altered while the app is running. Do this before the publish call
            //in case one of the subscribers throws an error.
            this.timeoutId = setTimeout(dojo.hitch(this, "fetch"), this.interval);

            //Notify of the first autosync, in case current sync info
            //wants to be shown.
            if (!this.didFirstNotify) {
                rd.pub("rd/autoSync-first", doc);
                this.didFirstNotify = true;
            }

            //Notify if there is a change in the info
            if (lastTimestamp && doc.timestamp !== lastTimestamp && doc.new_items) {
                rd.pub("rd/autoSync-update", doc);
            }
        },

        /**
         * Callback from XHR call for errors.
         * @param {Object} Error
         */
        _error: function (err) {
            rd.pub("rd/autoSync-error", err);
        }
    };

    autoSync.fetch();

    return autoSync;
});

    
    