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
        ["require", "dojo", "dojo/DeferredList", "rd", "rd/api", "rdw/placeholder", "rd/onHashChange"],
function (require,   dojo,   DeferredList,        rd,   api,      placeholder) {

    var validHashRegExp = /^\w+$/;

    //Set up hashchange listener
    rd.sub("rd/onHashChange", function (value) {
        value = value || "welcome";
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

    require.ready(function () {

        dojo.query(".oauthForm")
            .onsubmit(function (evt) {
                //First clear old errors
                dojo.query(".error").addClass("invisible");
    
                var form = evt.target,
                    isError = false;
    
                //Make sure all form elements are trimmed and username exists.
                dojo.forEach(form.elements, function (node) {
                    var trimmed = dojo.trim(node.value);
                    
                    if (node.getAttribute("placeholder") === trimmed) {
                        trimmed = "";
                    }

                    if (!trimmed && node.name === "username") {
                        isError = true;
                    } else if (trimmed && node.name === "addresses") {
                        //Make sure there are no spaces between the commas
                        node.value = trimmed.split(/\s*,\s*/).join(",");
                    }
                    node.value = trimmed;
                });
    
                if (isError) {
                    dojo.query(".usernameError", form).removeClass("invisible");
                    placeholder(form);
                    dojo.stopEvent(evt);
                }
            })
            .forEach(function (node) {
                placeholder(node);
            });
    });
});
