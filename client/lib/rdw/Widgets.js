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

/*jslint nomen: false, plusplus: false */
/*global require: false, setTimeout: false */
"use strict";

require.def("rdw/Widgets",
["rd", "dojo", "dojox", "rdw/_Base", "rd/api", "rd/api/message",
 "rdw/GenericGroup", "rdw/SummaryGroup", "dojo/fx", "dojox/fx/scroll", "rdw/GroupRss"],
function (rd, dojo, dojox, Base, api, message, GenericGroup, SummaryGroup, fx, fxScroll) {

    //Reassign fxScroll to be the real function, that module does something non-standard.
    fxScroll = dojox.fx.smoothScroll;

    return dojo.declare("rdw.Widgets", [Base], {
        //List of modules that can handle display of a summary.
        //It is assumed that moduleName.prototype.canHandleGroup(group) is defined
        //for each entry in this array.
        summaryModules: [
            "rdw/GroupRss"                 
        ],
    
        //Widget used for default group widgets, when no other group is applicable.
        summaryCtorName: "rdw/GenericGroup",

        //Widget used for the summary group widget, the first one in the widget list.
        summaryGroupCtorName: "rdw/SummaryGroup",
    
        templateString: '<div class="rdwWidgets"></div>',
  
        /** Dijit lifecycle method after template insertion in the DOM. */
        postCreate: function () {
            this.subscribe("rd-impersonal-add", "impersonalAdd");

            this._groups = [];

            if (!this.groupWidgets) {
                require(this.summaryModules, (dojo.hitch(this, function () {
                    this.groupWidgets = [];
                    var i, module, mod;
                    for (i = 0; (module = this.summaryModules[i]); i++) {
                        mod = require(module);
                        this.groupWidgets.push(mod);
                    }
                    this.destroyAllSupporting();
                    this.getData();
                })));
            } else {
                this.destroyAllSupporting();
                this.getData();
            }
        },

        /**
         * Dijit lifecycle method. Be sure to get rid
         * of anything we do not want if this widget is re-instantiated,
         * like for on-the-fly extension purposes.
         */
        destroy: function () {
            if (this.activeNode) {
                delete this.activeNode;
            }
            if (this.activeParentNode) {
                delete this.activeParentNode;
            }
            if (this.summaryActiveNode) {
                delete this.summaryActiveNode;
            }
            if (this.summaryWidget) {
                //This is also a supporting widget,
                //so no need to destroy it, just remove
                //the ref.
                delete this.summaryWidget;
            }

            this.inherited("destroy", arguments);
        },

        /**
         * Adds another summary based on the conversations passed. Called as a result of the
         * rd-impersonal-add topic. Synthesizes a "rd.grouping.info" schema based
         * on the passed in conversations and redraws the group summary widgets.
         * 
         * @param {Array} conversations
         */
        impersonalAdd: function (conversations) {
            //The home view groups messages by type. So, for each message in each conversation,
            //figure out where to put it.
            if (conversations && conversations.length) {
                //Create an rd.group.info schema. Choose the first conversation's
                //first message as the basis.
                var i, unread = [], convo,
                    body = conversations[0].messages[0].schemas["rd.msg.body"],
                    summary = {
                        rd_key: [['identity'], body.from],
                        rd_schema_id: 'rd.grouping.info',
                        // is grouping_tags necessary for the front-end?
                        grouping_tags: ['identity-' + body.from.join('-')],
                        title: body.from_display
                    };

                //Figure out how many unread messages there are.
                for (i = 0; (convo = conversations[i]); i++) {
                    if (convo.unread) {
                        unread.push(convo);
                    }
                }

                //Only worry about rendering if we have unread conversations to show.
                if (unread.length) {
                    //Add the conversations to the schema. This is not part
                    //of the formal schema definition, just helps out to pass
                    //it with the schema.
                    summary.conversations = unread;
                    summary.num_unread = unread.length;
                    this.render([summary]);
                }
            }
        },

        /**
         * Does the API call to get data, then calls rendering.
         */
        getData: function () {
            return api({
                url: 'inflow/grouping/summary'
            }).ok(this, "render");
        },

        /**
         * Does the actual display of the group widgets. It can be called multiple
         * times, but it does not remove older summaries that have been rendered.
         * The idea is to additively add new summaries, as when a "move to bulk"
         * action occurs.
         * 
         * @param {Array} summaries the array of "rd.grouping.info" schema summaries.
         */
        render: function (summaries) {
            if (summaries && summaries.length) {
                var i, summary, Handler, widget, frag, zIndex,
                SummaryWidgetCtor, group, key;

                //Weed out items that are not useful to this widget.
                for (i = 0; (summary = summaries[i]); i++) {
                    key = summary.rd_key;
                    // ignore 'inflow' and 'sent' and things with no unread count.
                    if ((key[0] === 'display-group' && (key[1] === 'inflow' || key[1] === 'sent')) ||
                        !summary.num_unread) {
                        continue;
                    }

                    //Create new group for each summary.
                    Handler = this._getGroup(summary);
                    if (Handler) {
                        widget = new Handler({
                            summary: summary
                        }, dojo.create("div"));
                        widget._isGroup = true;
                        this._groups.push(widget);
                        this.addSupporting(widget);
                    } else {
                        widget = this.createDefaultGroup(summary);
                        this._groups.push(widget);
                        this.addSupporting(widget);
                    }
                }
            }

            this._groups.sort(function (a, b) {
                var aSort = "groupSort" in a ? a.groupSort : 100,
                        bSort = "groupSort" in b ? b.groupSort : 100;
                return aSort > bSort ? 1 : -1;
            });

            frag = dojo.doc.createDocumentFragment();
            zIndex = this._groups.length;

            //Create summary group widget and add it first to the fragment.
            if (!this.summaryWidget) {
                SummaryWidgetCtor = require(this.summaryGroupCtorName);
                this.summaryWidget = new SummaryWidgetCtor();
                //Want summary widget to be the highest, add + 1 since group work
                //below uses i starting at 0.
                this.addSupporting(this.summaryWidget);
                this.summaryWidget.placeAt(frag);
            }

            //Add all the widgets to the DOM and ask them to display.
            this.summaryWidget.domNode.style.zIndex = zIndex + 1;
            for (i = 0; (group = this._groups[i]); i++) {
                group.domNode.style.zIndex = zIndex - i;
                group.placeAt(frag);
            }

            //Inject nodes all at once for best performance.
            this.domNode.appendChild(frag);
        },

        /**
         * Creates a default widget for a summary. The widget
         * should not display itself immediately since prioritization of the
         * widgets still needs to be done. Similarly, it should not try to attach
         * to the document's DOM yet. Override for more custom behavior/subclasses.
         * @param {Object} summary
         * @returns {rdw/Conversation} an rdw/Conversation or a subclass of it.
         */ 
        createDefaultGroup: function (summary) {
            return new (require(this.summaryCtorName))({
                summary: summary
            }, dojo.create("div"));
        },

        /**
         * Determines if there is a group widget that can handle the summary.
         * @param {Object} summary
         * @returns {rdw/Conversation} can return null
         */
        _getGroup: function (summary) {
            for (var i = 0, module; (module = this.groupWidgets[i]); i++) {
                if (module.prototype.canHandleGroup(summary)) {
                    return module;
                }
            }
            return null;
        }
    });
});
