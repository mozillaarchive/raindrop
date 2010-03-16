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

require.def("inflow",
[
    "require", "dojo", "dijit", "rd",
    "dojo/parser",
    "rd/accountIds",
    "rd/onHashChange",
    "rdw/Loading",
    "rdw/Notify",
    "rdw/QuickCompose",
    "rdw/Search",
    "rdw/Summary",
    "rdw/Conversations",
    "rdw/Widgets",
    "rdw/Organizer",
    "rd/engine",
    "rd/conversation"
],
function (require, dojo, dijit, rd, parser, accountIds) {
    //Do not do this work if inflow is not the main app.
    //This code can get loaded in other pages once an optimization
    //buld is done.
    if (rd.appName !== "inflow") {
        return null;
    }

    //If no account IDs, then just redirect to signup.
    if (!accountIds || !accountIds.length) {
        location.replace("../signup/index.html");
    }

    var inflow = {};

    dojo.mixin(inflow, {
        isComposeVisible: true,
    
        showQuickCompose: function () {
            //Place the div really high and slide it in.
            var qc, position, navNode;
            if (!this.isComposeVisible) {
                qc = dijit.registry.byClass("rdw.QuickCompose").toArray()[0];
                dojo.removeClass(qc.domNode, "invisible");
    
                position = dojo.position(qc.domNode);
                navNode = dojo.byId("nav");
                qc.domNode.style.top = (-1 * position.h) + "px";
                this.isComposeVisible = true;
                dojo.anim("nav", { top: 0 });
            }
        },

        hideQuickCompose: function () {
            if (this.isComposeVisible) {
                var qc = dijit.registry.byClass("rdw.QuickCompose").toArray()[0],
                    navPosition = dojo.marginBox(dojo.byId("nav")),
                    navHeaderPosition = dojo.marginBox(dojo.byId("navHeader"));

                this.isComposeVisible = false;
                dojo.anim("nav", { top: (-1 * (navPosition.h - navHeaderPosition.h)) });
            }
        },

        addNotice: function (node) {
            //Adds a notice to the notices area. Extensions can pass a DOM node
            //to this method to have it show up in the notices area. The caller
            //of this function is responsible for cleaning up the node. The node
            //should have a class="notice" for styling concerns.
            dojo.byId("notices").appendChild(node);
        }
    });

    //Set the window name, so extender can target it.
    //TODO: need to make this more generic, to work across raindrop apps.
    window.name = "raindrop";

    //Do onload work that shows the initial display.
    require.ready(function () {
        //Start page parsing of widgets.
        parser.parse();

        //In case parsing triggered loading of other widgets, wait for other widgets
        //to be defined before triggering the rest of this work.
        require(function () {
            //inflow.hideQuickCompose();

            //Trigger the first list of items to show. Favor a fragment ID on the URL.
            var fragId = location.href.split("#")[1], autoSync = 0,
                args = location.href.split("#")[0].split("?")[1];
            if (fragId) {
                rd.dispatchFragId(fragId);
            }

            //Listen for hash changes but only if the hash value is empty,
            //which means do our default action (view home)
            rd.sub("rd/onHashChange", function (val) {
                if (!val) {
                    rd.pub("rd-protocol-home");
                }
            });
    
            //Listen for quick compose open calls        
            //dojo.query(".quickComposeLaunch").onclick(function(evt) {
            //    inflow.showQuickCompose();
            //    dojo.stopEvent(evt);
            //})
    
            //Listen for quick compose close calls.
            //rd.sub("rd-QuickCompose-closed", inflow, "hideQuickCompose");
    
            //Start up the autosyncing if desired, time is in seconds.
            if (args) {
                args = dojo.queryToObject(args);
                if (args.autosync) {
                    if (args.autosync === "off") {
                        autoSync = 0;
                    } else {
                        autoSync = parseInt(args.autosync, 10);
                    }
                }
            }
    
            //watch for auto sync
            if (autoSync) {
                rd.engine.autoSync(autoSync);
            }
        });
    });
    
    return inflow;
});
