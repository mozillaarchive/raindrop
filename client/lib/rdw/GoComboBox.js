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

require.def("rdw/GoComboBox",
           ["rd", "dojo", "rdw/GoMatchMenu", "dijit", "dijit/form/ComboBox", "dijit/form/_FormWidget"],
function    (rd,   dojo,   GoMatchMenu,       dijit) {

    return dojo.declare("rdw.GoComboBox", [dijit.form._FormValueWidget, dijit.form.ComboBoxMixin], {
        postCreate: function () {
            this.inherited("postCreate", arguments);
        },

        onGoFocus: function(evt) {
            this.parentWidget.onGoFocus(evt);
        },

        /**
         * Bulk copy of dijit.form.ComboBoxMixin, but avoids calling dijit.popup
         * since we want the result list to show somewhere else.
         */
        open: function(){
            dojo.style(this.matchContainerNode, "display", "");
            this._isShowingNow = true;
        },

        /**
         * Required method for use in this widget's base class/mixin
         */
        displayMessage: function(text) {
        },

        /**
         * Required method for use in this widget's base class/mixin
         */
        validate: function() {
        },


        /**
         * Required method for use in this widget's base class/mixin
         */
        _refreshState: function() {
        },

        _openResultList: function(results, dataObject) {
            var parent = this.parentWidget;
            parent.onOpen();
            results = parent.sortResultsByType(results);
            parent.onDataStoreResults(results);

            return dijit.form.ComboBoxMixin.prototype._openResultList.apply(this, [results, dataObject]);
            //return this.inherited("_openResultList", [results, dataObject]);
        },

        _onKeyPress: function(evt) {
            var key = evt.charOrCode, keys = dojo.keys;

            if (key === keys.ESCAPE || key === keys.ENTER) {
                this._reallyClose = true;
            } else {
                this._reallyClose = false;
            }
            return this.inherited("_onKeyPress", arguments);
        },

        /**
         * Bulk copy of dijit.form.ComboBoxMixin, but avoids calling dijit.popup
         * since we want the result list to show somewhere else.
         */
        _hideResultList: function(){
            this._abortQuery();
            if(this._isShowingNow){
                //Start Raindrop change: dijit.popup would call onClose on
                //ComboBox mixin and that would call _blurOptionNode, but since
                //dijit.popup is not used, that work is done here.
                this._popupWidget._blurOptionNode();
                this._popupWidget.onClose();
                if (this._reallyClose) {
                    dojo.style(this.matchContainerNode, "display", "none");
                    this.parentWidget.onClose();
                }
                //End Raindrop change
                this._arrowIdle();
                this._isShowingNow=false;
                dijit.setWaiState(this.comboNode, "expanded", "false");
                dijit.removeWaiState(this.focusNode,"activedescendant");
            }
        },

        /**
         * Just a bulk copy of dijit.form.ComboBoxMixin's _startSearch, but
         * want to change the widget used for the _popupWidget. A bit of a waste
         * but dijit.form.ComboBoxMixin does not allow setting what widget to use
         * for the _popupWidget.
         */
        _startSearch: function(/*String*/ key){
            if(!this._popupWidget){
                var popupId = this.id + "_popup";
                //Changed for Raindrop
                this._popupWidget = new GoMatchMenu({
                    onChange: dojo.hitch(this, this._selectOption),
                    id: popupId
                    //Added for Raindrop
                }, dojo.create("div", null, this.matchContainerNode));
                dijit.removeWaiState(this.focusNode,"activedescendant");
                dijit.setWaiState(this.textbox,"owns",popupId); // associate popup with textbox
            }
            // create a new query to prevent accidentally querying for a hidden
            // value from FilteringSelect's keyField
            var query = dojo.clone(this.query); // #5970
            this._lastInput = key; // Store exactly what was entered by the user.
            this._lastQuery = query[this.searchAttr] = this._getQueryString(key);
            // #5970: set _lastQuery, *then* start the timeout
            // otherwise, if the user types and the last query returns before the timeout,
            // _lastQuery won't be set and their input gets rewritten
            this.searchTimer=setTimeout(dojo.hitch(this, function(query, _this){
                this.searchTimer = null;
                var fetch = {
                    queryOptions: {
                        ignoreCase: this.ignoreCase,
                        deep: true
                    },
                    query: query,
                    onBegin: dojo.hitch(this, "_setMaxOptions"),
                    onComplete: dojo.hitch(this, "_openResultList"),
                    onError: function(errText){
                        _this._fetchHandle = null;
                        console.error('dijit.form.ComboBox: ' + errText);
                        dojo.hitch(_this, "_hideResultList")();
                    },
                    start: 0,
                    count: this.pageSize
                };
                dojo.mixin(fetch, _this.fetchProperties);
                this._fetchHandle = _this.store.fetch(fetch);

                var nextSearch = function(dataObject, direction){
                    dataObject.start += dataObject.count*direction;
                    // #4091:
                    //        tell callback the direction of the paging so the screen
                    //        reader knows which menu option to shout
                    dataObject.direction = direction;
                    this._fetchHandle = this.store.fetch(dataObject);
                };
                this._nextSearch = this._popupWidget.onPage = dojo.hitch(this, nextSearch, this._fetchHandle);
            }, query, this), this.searchDelay);
        }
    });
});
