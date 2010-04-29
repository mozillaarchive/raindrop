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
    var dndSource, newFolderNode, dndTargets = [],

        tooltip = {
            template: '<div class="bulkEditTooltip">Merge these two items into new folder</div>',
            show: function (node) {
                if (!tooltip.node) {
                    tooltip.node = dojo.place(tooltip.template, dojo.body());
                }

                tooltip.node.style.display = "block";
                dijit.placeOnScreenAroundElement(tooltip.node, node, {"TL": "BL"});
            },

            hide: function () {
                tooltip.node.style.display = "none";
            }
        };

    function makeTarget(node) {
        var target = new dojo.dnd.Target(node);
        target.onDraggingOver = function () {
            tooltip.show(node);
        };
        target.onDraggingOut = function () {
            tooltip.hide();
        };
        target.onDrop = function (source, nodes, copy) {
            //Do not do anything for right now.
            tooltip.hide();
        };
        return target;
    }

    require.ready(function () {
        dojo.query(".bulkEditButton", dojo.byId("top")).onclick(function () {
            var widget = dijit.byId("widgets"),
                domNode = widget.containerNode,
                widgetBoxes = dojo.query(".WidgetBox", domNode);

            //Pull out the first widget box, which is the summary box.
            widgetBoxes.splice(0, 1);

            if (dojo.hasClass(domNode, "bulkEdit")) {
                widgetBoxes.anim({marginTop: -30}, 1000, null, function () {
                    widgetBoxes.style("marginTop", "");
                });
                dojo.removeClass(domNode, "bulkEdit");
                if (dndSource) {
                    dndSource.destroy();
                    dndSource = null;
                    widgetBoxes.removeClass("dojoDndItem");
                }
                if (dndTargets.length) {
                    dndTargets.forEach(function (target) {
                        target.destroy();
                    })
                }

                newFolderNode.parentNode.removeChild(newFolderNode);

            } else {
                widgetBoxes.anim({marginTop: 20}, 1000);
                dojo.addClass(domNode, "bulkEdit");

                //Set up DND
                dndTargets = [];
                widgetBoxes.forEach(function (node) {
                    dojo.addClass(node, "dojoDndItem");
                    dndTargets.push(makeTarget(node));
                });
                dndSource = new Source(domNode);

                //Put in the New Folder item
                if (!newFolderNode) {
                    newFolderNode = dojo.place('<div class="newFolderContainer">Create new folder</div>', domNode);
                    dojo.connect(newFolderNode, "onclick", function (evt) {
                        console.log("clicked");
                    });
                } else {
                    dojo.place(newFolderNode, domNode);
                }
            }
        });
    });
});
