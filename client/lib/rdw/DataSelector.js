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
/*global require: false, document: false */
"use strict";

require.def("rdw/DataSelector",
["require", "rd", "dojo", "dojo/DeferredList", "rdw/_Base", "i18n!rdw/nls/i18n", "rd/MegaviewStore", "rdw/GoComboBox",
 "text!rdw/templates/DataSelector.html"],
function (require, rd, dojo, DeferredList, Base, i18n, MegaviewStore, GoComboBox, template) {

    return dojo.declare("rdw.DataSelector", [Base], {
        templateString: template,
    
        typeItemTemplate: '<li data-type="${type}">${name} <button name="remove-type-filter">' + i18n.removeFilter + '</button></li>',

        comboWidget: "rdw/GoComboBox",

        //type can have values of "identityContact", "contact", or "locationTag"
        //by default. Extensions can add other types by creating a typeLoaded function
        //on this widget.
        type: "identityContact",
    
        //If type is set to "all", this is the list of data stores
        //to aggregate together. Extensions can add other types by pushing
        //new values to this array. Note that this is an array on the prototype for
        //this widget. Just reassign this property to a new array on an instance
        //just to affect that instance's list.
        allType: ["contact", "locationTag"],
    
        //Restrict the type of records further. Useful in the default case only
        //for type: "identityContact".
        //values are like "twitter", "email", in other words, the first array
        //value of the identity ID.
        subType: "",
    
        //An initial value that will be used after
        //the person docs from the couch have loaded.
        initialValue: "",

        /** Keyboard shortcut to expand the UI */
        keyboardShortcut: "/",

        /** Dijit lifecycle method executed before template evaluated */
        postMixInProperties: function () {
            this.inherited("postMixInProperties", arguments);
        },

        /** Dijit lifecycle method executed after template HTML is in DOM */
        postCreate: function () {
            //Declare array to use for items found from data sources.
            this.items = [];
    
            //Figure out what data sources to use.
            this.sources = this.allType;
            if (this.type !== "all") {
                this.sources = [this.type];
            }

            //Create a fake widget that holds the uiNode.
            this.fakeUiWidget = {
                domNode: this.uiNode,
                onChange: function () {}
            };


            //Bind document-wide events that handle opening and closing of the
            //expanded UI.
            this.connect(document.documentElement, "onkeypress", "onDocKeyPress");
            this.connect(document.documentElement, "onclick", "onDocClick");
            
            this.createWidget();
        },

        /**
         * Handles clicks that will trigger showing the larger div with all the
         * choices.
         * @param {Event} evt
         */
        onClick: function (evt) {
            this.expand();
        },

        /**
         * Handles clicks to the types on the left side, to filter the results
         * by type, and to also remove the filter.
         * @param {Event} evt
         */
        onTypeClick: function (evt) {
            var name = evt.target.name,
                type = evt.target.getAttribute("data-type");

            if (name && name.indexOf("remove-type-filter") !== -1) {
                this.removeTypeFilter();
                dojo.stopEvent(evt);
            } else if (type) {
                this.addTypeFilter(type);
                dojo.stopEvent(evt);
            }
        },

        /**
         * creates the widget that will use the data in this.items. Each object
         * entry in items should have an "id" and a "name" property.
         */
        createWidget: function () {
            //sort by name
            this.items.sort(function (a, b) {
                return a.name > b.name ? 1 : -1;
            });

            //Load the code for the widget then create and initialize it.
            require([this.comboWidget], dojo.hitch(this, function (Ctor) {
                //Create the selector widget.
                this.selectorInstance = new Ctor({
                    matchContainerNode: this.matchContainerNode,
                    parentWidget: this,
                    store: new MegaviewStore({
                        schemaQueryTypes: this.sources,
                        subType: this.subType
                    }),
                    onChange: dojo.hitch(this, "onSelectorChange")            
                }, this.selectorNode);
    
                //Pass initial value to selector if it was set.
                if (this.initialValue) {
                    this.selectorInstance.attr("value", this.initialValue);
                }
        
                //Add to supporting widgets so widget destroys do the right thing.
                this.addSupporting(this.selectorInstance);
            }));
        },

        /**
         * Global keypress handler, used to know when to expand the UI.
         * @param {Event} evt
         */
        onDocKeyPress: function (evt) {
            if (evt.charOrCode === this.keyboardShortcut && !this.isExpanded) {
                this.expand(true);
            }
        },

        /**
         * Global click handler, used to know if user clicks outside the
         * expanded box then the UI should be collapsed. Only do this work
         * if the UI is expanded.
         * @param {Event} evt
         */
        onDocClick: function (evt) {
            if (this.isExpanded) {
                //If click is not within the widget close it.
                var isOutside = true, node = evt.target;
                while (node.parentNode) {
                    if (node.id === this.id) {
                        isOutside = false;
                        break;
                    }
                    node = node.parentNode;
                }

                if (isOutside) {
                    this.onClose();
                }
            }
        },

        /**
         * Triggered by GoComboBox when its text element is focused.
         */
        onGoFocus: function (evt) {
            this.expand();
        },

        onOpen: function () {
            this.expand();        
        },

        onClose: function () {
            if (this.isExpanded) {
                dojo.removeClass(this.domNode, "expanded");
                this.isExpanded = false;
            }
        },

        /**
         * Expands the UI.
         * @param {Boolean} shouldFocus if true, then the focus will be placed
         * in the combo box widget, if it is instantiated.
         */
        expand: function (shouldFocus) {
            if (!this.isExpanded) {
                dojo.addClass(this.domNode, "expanded");
                this.isExpanded = true;
            }

            //Focus in the text area, if desired
            if (shouldFocus && this.selectorInstance) {
                this.selectorInstance.focus();
            }

            //Trigger an "all" query if there are no results.
            if (this.selectorInstance && !this.selectorInstance.textbox.value) {
                this.selectorInstance._startSearchAll();
            }
        },

        /**
         * Called when there are results from the Data Store.
         * Use the results to know what types/categories to show on the
         * left side.
         * @param {Array} results
         */
        onDataStoreResults: function (results) {
            this.showTypeLabels(results);
        },

        typeLabels: {
            "contact": i18n.contactTypeLabel,
            "locationTag": i18n.locationTagTypeLabel
        },

        /** Given an array of MegaviewStore results, give back a list of unique types with their
         * labels, with items under that label, suitable for UI display.
         */
        sortResultsByType: function (results) {
            var labels = [], i, item, unique = {}, type, typeObj;
            for (i = 0; (item = results[i]); i++) {
                type = item.type;
                typeObj = unique[type];
                if (!unique[type]) {
                    labels.push({
                        type: type,
                        name: this.typeLabels[type] || type,
                        items: [item]
                    });
                    unique[type] = labels[labels.length - 1];
                } else {
                    typeObj.items.push(item);
                }
            }

            return labels;
        },

        showTypeLabels: function (labels) {
            var i, label, html = "";

            if (labels) {
                for (i = 0; (label = labels[i]); i++) {
                    html += rd.template(this.typeItemTemplate, label);
                }
            }

            this.typesNode.innerHTML = html;
        },

        addTypeFilter: function (type) {
            //First remove any previous filter
            this.removeTypeFilter();

            //Grab all the nodes match nodes and only show the one that
            //matches the selected type.
            dojo.query("[data-type]", this.domNode)
                .forEach(function (node) {
                    dojo.addClass(node, (node.getAttribute("data-type") === type ? "selected" : "unselected"));
                });
            
            this.selectedType = type;
        },

        removeTypeFilter: function () {
            dojo.query(".unselected", this.domNode).removeClass("unselected");
            dojo.query(".selected", this.domNode).removeClass("selected");
            this.selectedType = null;
        },

        /**
         * Triggered when the selector's value changes. value should be
         * type:id.
         * @param {String} value
         */
        onSelectorChange: function (value) {
            var item = this.selectorInstance.item;
            if (!item) {
                return;
            }
    
            //Dispatch to idSelected method on this instance.
            this[item.type + "Selected"](item.id);

            this.onDataSelected({
                type: item.type,
                id: item.id,
                value: item.name
            });

            this.onClose();
        },

        /**
         * Connection point for other code, that signals when data is selected.
         * @param {Object} data
         * @param {String} data.type the type of data selected (from what data source)
         * @param {String} data.id the id of the data for that type of data source.
         * @param {String} data.value the visible value for the data selected.
         */
        onDataSelected: function (/*Object*/data) {
        },

        /**
         * Allows instance.attr("value") to work.
         */
        _getValueAttr: function () {
            return this.selectorInstance ? this.selectorInstance.attr("value") : this.initialValue;
        },

        /**
         * Allows instance.attr("value", value) to work.
         */
        _setValueAttr: function (/*String*/ value, /*Boolean?*/ priorityChange) {
            return this.selectorInstance ?
                    this.selectorInstance.attr("value", value, priorityChange)
                :
                    this.initialValue = value;
        },

        /**
         * Dispatch function when a contact is selected.
         * @param {String} contactId
         */
        contactSelected: function (contactId) {
            rd.setFragId("rd:contact:" + contactId);    
        },

        /**
         * Dispatch function when an identity is selected.
         * @param {String} identityId
         */
        identitySelected: function (identityId) {
            rd.setFragId("rd:identity:" + identityId);
        },
    
        /**
         * Dispatch function when a locationTag is selected.
         * @param {String} location
         */
        locationTagSelected: function (location) {
            rd.setFragId("rd:locationTag:" + location);
        }
    });
});