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

require.def("bulkEdit",
        ["require", "dojo", "rd", "dijit", "dojo/dnd/Source", "dojo/NodeList-fx"],
function (require,   dojo,   rd,   dijit,   Source) {
    var dndSource;

    require.ready(function () {
        dojo.query(".bulkEditButton", dojo.byId("top")).onclick(function () {
            var widget = dijit.byId("widgets"),
                domNode = widget.domNode;
                widgetBoxes = dojo.query(".WidgetBox", domNode);

            //Pull out the first widget box, which is the summary box.
            widgetBoxes.splice(0, 1);

            if (dojo.hasClass(domNode, "bulkEdit")) {
                widgetBoxes.anim({marginTop: -30}, 1000, null, function () {
                    widgetBoxes.style("marginTop", "");
                });
                dojo.removeClass(domNode, "bulkEdit");
                //if (dndSource) {
                //    dndSource.destroy();
                //    dndSource = null;
                //    widgetBoxes.removeClass("dojoDndItem");
               // }
            } else {
                widgetBoxes.anim({marginTop: 20}, 1000);
                dojo.addClass(domNode, "bulkEdit");
                
                //Set up DND
                widgetBoxes.addClass("dojoDndItem");
                //dndSource = new Source(domNode);
            }
        });
    });
});
