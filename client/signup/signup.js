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
/*global require: false, location: true */
"use strict";

require.def("signup",
        ["require", "dojo", "dojo/DeferredList", "rd", "rd/api", "rd/onHashChange"],
function (require,   dojo,   DeferredList,        rd,   api) {

    var validHashRegExp = /^\w+$/;

    /**
     * Set the input value to use placeholder value if HTML5 placeholder
     * attribute is not supported.
     * @param {DOMNode} input an input element.
     */
    function setPlaceholder(input) {
        //If no native support for placeholder then JS to the rescue!
        var missingNative = !("placeholder" in input);

        if (!dojo.trim(input.value)) {
            dojo.addClass(input, "placeholder");
            if (missingNative) {
                input.value = input.getAttribute("placeholder");
            }
        } else {
            dojo.removeClass(input, "placeholder");
        }
    }

    //Set up hashchange listener
    rd.sub("rd/onHashChange", function (value) {
        value = value || "one";
        var startNode, endNode;

        if (validHashRegExp.test(value)) {
            dojo.query(".section").forEach(function (node) {
                if (dojo.hasClass(node, value)) {
                    endNode = node;
                } else if (!dojo.hasClass(node, "hidden")) {
                    startNode = node;
                }
            });
        }

        //Animate!
        if (startNode) {
            //Start node
            dojo.fadeOut({
                node: startNode,
                duration: 600,
                onEnd: function () {
                    dojo.addClass(startNode, "hidden");
                }
            }).play();
        }

        if (endNode) {
            //End node
            dojo.style(endNode, "opacity", 0);
            dojo.removeClass(endNode, "hidden");
            dojo.fadeIn({
                node: endNode,
                duration: 600
            }).play();
        }
    });


    /**
     * Sends the config info to the server to set up the accounts.
     * @config {Object} the config object with properties: gmailName, gmailPassword,
     * twitterName, twitterPassword
     */
    function send(config) {
        //API is very granular, build up options for each call: twitter,
        //gmail imap and gmail smtp.
        var dfds = [], dfdList;
        if (config.gmailName && config.gmailPassword) {
            //Make sure name has an @ in it:
            if (config.gmailName.indexOf("@") === -1) {
                config.gmailName += "@gmail.com";
            }

            //Set up IMAP to Gmail
            dfds.push(api({
                url: 'inflow/account/set?id=' + encodeURIComponent('"imap-gmail-' + config.gmailName + '"'),
                method: "POST",
                bodyData: dojo.toJson({
                    proto: "imap",
                    kind: "gmail",
                    host: "imap.gmail.com",
                    port: 993,
                    username: config.gmailName,
                    password: config.gmailPassword,
                    ssl: true
                })
            }).deferred());

            //Set up SMTP to Gmail
            dfds.push(api({
                url: 'inflow/account/set?id=' + encodeURIComponent('"smtp-gmail-' + config.gmailName + '"'),
                method: "POST",
                bodyData: dojo.toJson({
                    proto: "smtp",
                    host: "smtp.gmail.com",
                    port: 587,
                    username: config.gmailName,
                    password: config.gmailPassword,
                    ssl: false
                })
            }).deferred());
        }
        
        if (config.twitterName && config.twitterPassword) {
            //Set up Twitter
            dfds.push(api({
                url: 'inflow/account/set?id=' + encodeURIComponent('"twitter-' + config.twitterName + '"'),
                method: "POST",
                bodyData: dojo.toJson({
                    proto: "twitter",
                    kind: "twitter",
                    username: config.twitterName,
                    password: config.twitterPassword
                })
            }).deferred());            
        }

        //Wait for all the deferreds to return.
        dfdList = new DeferredList(dfds);
        dfdList.addCallbacks(
            dojo.hitch(this, function() {
                //Success case.
                location = '#three';
            }),
            dojo.hitch(this, function (err) {
                //Error case.
                alert(err);
            })
        );
    }

    require.ready(function () {

        dojo.query("#credentials")
            .onsubmit(function (evt) {
                //Handle form submissions for the credentials.
                //First clear old errors
                dojo.query(".error").addClass("invisible");
                
                //Make sure we have all the inputs.
                var ids = ["gmailName", "gmailPassword", "twitterName", "twitterPassword"],
                    i, id, value, node, isError = false, config = {};

                for (i = 0; (id = ids[i]) && (node = dojo.byId(id)); i++) {
                    value = dojo.trim(node.value);
                    if (!value || node.getAttribute("placeholder") === value) {
                        dojo.removeClass(dojo.byId(id + "Error"), "invisible");
                        isError = true;
                    } else {
                        config[node.id] = value;
                    }
                }

                if (!isError) {
                    send(config);
                }

                dojo.stopEvent(evt);
            })
            .query('input[type="text"]')
                //Set up initial state.
                .forEach(setPlaceholder)

                .onfocus(function (evt) {
                    //Clear out placeholder, change the style.
                    var input = evt.target;
                    if (input.value === input.getAttribute("placeholder")) {
                        if (!("placeholder" in input)) {
                            input.value = "";
                        }
                        dojo.removeClass(input, "placeholder");
                    }
                })

                .onblur(function (evt) {
                    //Reset placeholder text if necessary.
                    setPlaceholder(evt.target);
                });
    });
});
