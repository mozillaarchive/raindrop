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
/*jslint plusplus: false */
/*global require: false, window: false, location: false */
"use strict";

require.def("settings",
        ["require", "dojo", "rd", "settings/Account", "rd/api"],
function (require,   dojo,   rd,   Account,            api) {

    require.ready(function () {
        var allowed = [
            "gmail",
            "twitter"
        ];

        //Fetch all accounts and create widgets, but only for the allowed types.
        api().megaview({
            key: ["schema_id", "rd.account"],
            reduce: false,
            include_docs: true
        })
        .ok(function (json) {
            var settingsNode = dojo.byId("settings"), kindMap = {},
                i, row, doc, svc;

            //Build up a set of kind to doc mappings.
            for (i = 0; (row = json.rows[i]) && (doc = row.doc); i++) {
                if (doc.kind) {
                    kindMap[doc.kind] = doc;
                }
            }

            //Build a list of widgets for the allowed set, using documents if they exist
            //to populate them.
            for (i = 0; (svc = allowed[i]); i++) {
                doc = kindMap[svc] || {
                    kind: svc
                };

                (new Account({
                    doc: doc
                }, dojo.create("div", null, settingsNode)));
            }
            
        });
    });
});
