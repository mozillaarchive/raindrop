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
/*global require: false, setTimeout: false */
"use strict";

require.def("rdw/GoMatchMenu",
           ["rd", "dojo", "dijit", "dijit/form/ComboBox"],
function    (rd,   dojo,   dijit) {

    /**
     * An overrides of dijit.form._ComboBoxMenu, with lots of copy/pasting of
     * properties to do specific overrides.
     */
    return dojo.declare("rdw.GoMatchMenu", [dijit.form._ComboBoxMenu], {
        
        templateString: "<ul class='dijitReset' dojoAttachEvent='onmousedown:_onMouseDown,onmouseup:_onMouseUp,onmouseover:_onMouseOver,onmouseout:_onMouseOut' tabIndex='-1' style='overflow: \"auto\"; overflow-x: \"hidden\";'>" +
                            "<li class='dijitMenuItem dijitMenuPreviousButton' style='display: none' dojoAttachPoint='previousButton' waiRole='option'></li>" +
                            "<li class='dijitMenuItem dijitMenuNextButton' style='display: none' dojoAttachPoint='nextButton' waiRole='option'></li>" +
                        "</ul>",

        _createOption: function(/*Object*/ item, labelFunc){
            // summary:
            //        Creates an option to appear on the popup menu subclassed by
            //        `dijit.form.FilteringSelect`.

            var labelObject = labelFunc(item),
                menuitem = dojo.doc.createElement("li"),
                headerNode = dojo.create('h4', null, menuitem),
                matches = item.items, matchNode, listNode,
                i, match, html = '', id;

            
            if (labelObject.html) {
                headerNode.innerHTML = labelObject.label;
            } else {
                headerNode.appendChild(
                    dojo.doc.createTextNode(labelObject.label)
                );
            }

            if (matches.length) {
                listNode = dojo.create('ul');
            }

            for (i = 0; (match = matches[i]); i++) {
                matchNode = dojo.create('li', {
                    id: 'GoMatchMenu_' + item.type + '_sub_' + i,
                    'class': 'dijitReset dijitMenuItem rdwGoMatchMenuRealOption',
                    innerHTML: rd.escapeHtml(match.name.toString())
                }, listNode);

                dijit.setWaiRole(matchNode, "option");

                //Store the match object on the node so super class knows
                //it is a valid option and gets its value.
                matchNode.item = match;
            }

            if (matches.length) {
                dojo.place(listNode, menuitem);
            }

            // #3250: in blank options, assign a normal height
            if (menuitem.innerHTML == "") {
                menuitem.innerHTML = "&nbsp;";
            }

            return menuitem;
        },

        createOptions: function(results, dataObject, labelFunc) {
            dojo.forEach(results, function(typedItem, i) {
                var menuitem = this._createOption(typedItem, labelFunc);
                menuitem.className = "dijitReset";
                dojo.attr(menuitem, "id", this.id + i);
                this.domNode.insertBefore(menuitem, this.nextButton);
            }, this);

            return this.domNode.childNodes;
        },

        _getRealOptions: function() {
            return dojo.query('.rdwGoMatchMenuRealOption', this.domNode);
        },

        _highlightNextOption: function(){
            // summary:
            //         Highlight the item just below the current selection.
            //         If nothing selected, highlight first option.

            // because each press of a button clears the menu,
            // the highlighted option sometimes becomes detached from the menu!
            // test to see if the option has a parent to see if this is the case.
            var nodes = this._getRealOptions(), index;
            if(!this.getHighlightedOption()){
                this._focusOptionNode(nodes[0]);
            }else{
                index = nodes.indexOf(this._highlighted_option) + 1;
                if (index > nodes.length - 1) {
                    index = 0;
                }
                this._focusOptionNode(nodes[index]);
            }
            // scrollIntoView is called outside of _focusOptionNode because in IE putting it inside causes the menu to scroll up on mouseover
            dijit.scrollIntoView(this._highlighted_option);
        },

        highlightFirstOption: function(){
            // summary:
            //         Highlight the first real item in the list (not Previous Choices).
            this._focusOptionNode(this._getRealOptions()[0]);            
            dijit.scrollIntoView(this._highlighted_option);
        },

        highlightLastOption: function(){
            // summary:
            //         Highlight the last real item in the list (not More Choices).
            
            var nodes = this._getRealOptions();
            this._focusOptionNode(nodes[nodes.length - 1]);
            dijit.scrollIntoView(this._highlighted_option);
        },

        _highlightPrevOption: function(){
            // summary:
            //         Highlight the item just above the current selection.
            //         If nothing selected, highlight last option (if
            //         you select Previous and try to keep scrolling up the list).
            var nodes = this._getRealOptions(), index;

            if(!this.getHighlightedOption()){
                this._focusOptionNode(nodes[nodes.length - 1]);
            }else{
                index = nodes.indexOf(this._highlighted_option) - 1;
                if (index < 0) {
                    index = nodes.length - 1;
                }
                this._focusOptionNode(nodes[index]);
            }
            dijit.scrollIntoView(this._highlighted_option);
        },

        _onMouseOver: function(/*Event*/ evt){
            if(evt.target === this.domNode){ return; }
            var tgt = evt.target;
            if(!(tgt == this.previousButton || tgt == this.nextButton)){
                // while the clicked node is inside the div
                while(!tgt.item && tgt !== this.domNode){
                    // recurse to the top
                    tgt = tgt.parentNode;
                }
            }
            if (tgt && tgt.item) {
                this._focusOptionNode(tgt);
            }
        },

        _onMouseOver: function(/*Event*/ evt){
            if(evt.target === this.domNode){ return; }
            var tgt = evt.target;
            if(!(tgt == this.previousButton || tgt == this.nextButton)){
                // while the clicked node is inside the div
                while(!tgt.item && tgt !== this.domNode){
                    // recurse to the top
                    tgt = tgt.parentNode;
                }
            }
            if (tgt && tgt.item) {
                this._focusOptionNode(tgt);
            }
        }


    });
});
