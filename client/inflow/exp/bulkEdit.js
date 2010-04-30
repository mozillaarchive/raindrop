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

/*jslint plusplus: false, regexp: false, nomen: false */
/*global require: false, window: false, location: false, document: false */
"use strict";

require.def("bulkEdit",
        ["require", "dojo", "rd", "dijit", "dojo/dnd/Source", "rdw/Folder", "dojo/NodeList-fx"],
function (require,   dojo,   rd,   dijit,   Source,            Folder) {
    var dndSource, dndConvSource, newFolderNode, dndTargets = [], clickDisableHandle,

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
                if (tooltip.node) {
                    tooltip.node.style.display = "none";
                }
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
            var folderWidget, widget = dijit.byId("widgets"),
                dropWidget = dijit.getEnclosingWidget(node),
                dragWidget = dijit.getEnclosingWidget(nodes[0]);

            tooltip.hide();

            //Create a new folder widget
            folderWidget = new Folder({
                summary: {
                    title: "foo"
                }
            }, dojo.create("div"));
            folderWidget.domNode.style.zIndex = node.style.zIndex;
            folderWidget.placeAt(node, "after");
            widget.addSupporting(folderWidget);

            //Destroy the old widgets
            widget.removeSupporting(dropWidget);
            dropWidget.destroy();
            widget.removeSupporting(dragWidget);
            dragWidget.destroy();

            //focus in the edit for the folder.
            folderWidget.showNameInput();
        };
        return target;
    }

    require.ready(function () {
        dojo.query(".bulkEditButton", dojo.byId("top")).onclick(function () {
            var widget = dijit.byId("widgets"),
                conversationsListNode = dijit.byId("conversations").listNode,
                domNode = widget.containerNode,
                widgetBoxes = dojo.query(".WidgetBox", domNode),
                convWidgetNodes = dojo.query(".rdwConversation", conversationsListNode);

            //Pull out the first widget box, which is the summary box.
            widgetBoxes.splice(0, 1);

            if (dojo.hasClass(domNode, "bulkEdit")) {
                widgetBoxes.anim({marginTop: -30}, 1000, null, function () {
                    widgetBoxes.style("marginTop", "");
                    dojo.removeClass(domNode, "bulkEditExpanded");
                });

                //Remove global click disable
                if (clickDisableHandle) {
                    dojo.disconnect(clickDisableHandle);
                }

                //Clean up conversation DND
                if (dndConvSource) {
                    dndConvSource.destroy();
                    dndConvSource = null;
                    convWidgetNodes.removeClass("dojoDndItem");
                    dojo.removeClass(conversationsListNode, "dragCursor");
                }

                //Clean up widget edit state and DND
                dojo.removeClass(domNode, "bulkEdit");
                if (dndSource) {
                    dndSource.destroy();
                    dndSource = null;
                    widgetBoxes.removeClass("dojoDndItem");
                    dojo.removeClass(domNode, "dragCursor");
                }
                if (dndTargets.length) {
                    dndTargets.forEach(function (target) {
                        target.destroy();
                    });
                }

                newFolderNode.parentNode.removeChild(newFolderNode);

            } else {
                widgetBoxes.anim({marginTop: 20}, 1000, null, function() {
                    dojo.addClass(domNode, "bulkEditExpanded");
                });
                dojo.addClass(domNode, "bulkEdit");

                //Disable A tags from changing the source. This is a bit crude,
                //does not capture everything, but it is something quick and
                //easy to do.
                clickDisableHandle = dojo.connect(document.documentElement, "onclick", function (evt) {
                    if (evt.target.nodeName.toUpperCase() !== "INPUT") {
                        evt.preventDefault();
                    }
                });

                //Set up DND for conversation widgets
                convWidgetNodes.addClass("dojoDndItem");
                dndConvSource = new Source(conversationsListNode, {
                    //Do not allow this source to accept items
                    accept: [],
                    creator: function (item, hint) {
                        //item is a string of HTML, pick out the from name from it.
                        var name = /fromNode"[^>]*>([^<]+)</.exec(item)[1];

                        return {
                            node: dojo._toDom('<div class="bulkEditConvDrag">Drag "' + name + '" to bulk</div>'),
                            data: item
                            //type?
                        };
                    }
                });
                dojo.addClass(conversationsListNode, "dragCursor");

                //Set up DND on Widgets widget
                dndTargets = [];
                widgetBoxes.forEach(function (node) {
                    dojo.addClass(node, "dojoDndItem");
                    dndTargets.push(makeTarget(node));
                });
                dndSource = new Source(domNode);
                dojo.addClass(domNode, "dragCursor");

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
