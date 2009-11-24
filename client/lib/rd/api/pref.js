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

dojo.provide("rd.api.pref");

dojo.require("rd.api");

/**
 * Gets preferences for a preference ID.
 *
 * @param {dojo.Deferred} dfd the deferred to use for the rd.api() call.
 *
 * @param {Object} args. The args for the API call.
 * @param {String} args.id the preference ID. Preference IDs for JavaScript modules
 * or components/widgets should take the form of
 * componentName, componentName:appName, or componentName:appName:instanceId.
 * If the prefId has : parts, then all prefs for the name that have fewer
 * : parts will be loaded at the same time. So, if componentName:appName:instanceId
 * is asked for, then componentName:appName and componentName prefs will also
 * be requested. The more specific name's preferences will take priority
 * over less specific names.
 * 
 * @param {Object} args.prefs the prefs object to save to the server. Optional,
 * do not pass it if you just want to read the prefs from the server.
 */
rd.api.pref = function(dfd, args, prefId) {
  return rd.api.pref[(args.prefs ? "set" : "get")](dfd, args, prefId);
};

dojo._mixin(rd.api.pref, {
  _key: function(prefId) {
    return ['rd.core.content', 'key-schema_id', [["pref", prefId], "rd.pref"]];
  },

  get: function(dfd, args, prefId) {
    //First break down the prefId.
    var parts = prefId.split(":");
    var name = parts[0];
    var prefNames = [name];
    var keys = [this._key(name)];
    for (var i = 1; i < parts.length; i++) {
      name += ":" + parts[1];
      prefNames.push(name);
      keys.push(this._key(name));
    }
  
    rd.api().megaview({
      keys: keys,
      include_docs: true,
      reduce: false
    })
    .ok(function(json) {
      var prefs = {},
          docs = {},
          isEmpty = true;
      //first, conver the json returned values into an object keyed by
      //rd_key value so they are applied to prefs in the right order.
      for (var i = 0, row, doc; (row = json.rows[i]) && (doc = row.doc); i++) {
        isEmpty = false;
        docs[doc.rd_key[1]] = doc;
      }
  
      if (!isEmpty) {
        //Now cycle through the previously generated keys to get the
        //pref names that should be applied in order, and mixin the prefs
        //for each pref name into the final result.
        for (var i = 0, prefName; prefName = prefNames[i]; i++) {
          var temp = docs[prefName];
          if (temp) {
            dojo._mixin(prefs, temp);
          }
        }
      }
  
      dfd.callback(isEmpty ? null : prefs);
    })
    .error(dfd);
  },

  set: function(dfd, args, prefId) {
    var prefs = args.prefs;

    //First, see if there is an existing doc, to get its _rev and possibly its
    //_id.
    var api = rd.api().megaview({
      key: this._key(prefId),
      include_docs: true,
      reduce: false
    })
    .ok(function(json) {
      var doc = (json.rows[0] && json.rows[0].doc) || {};
  
      //Favor existing doc for ID.
      if (doc._id) {
        prefs._id = doc._id;
      }
  
      if (doc._rev && prefs._rev != doc._rev) {
        var err = new Error("rd.docOutOfDate");
        err.currentRev = doc._rev;
        dfd.errback(err);
        return;
      }
  
      //Fill in any rd_* properties
      if (!prefs.rd_key) {
        prefs.rd_key = doc.rd_key || ["pref", prefId];
      }
      if (!prefs.rd_source) {
        prefs.rd_source = doc.rd_source || null;
      }
      if (!prefs.rd_schema_id) {
        prefs.rd_schema_id = doc.rd_schema_id || "rd.pref";
      }
      if (!prefs.rd_ext_id) {
        prefs.rd_ext_id = doc.rd_ext_id;
      }

      //Save the pref.
      var saveApi = rd.api().put({
        doc: prefs
      }).ok(dfd).error(dfd);
    })
    .error(dfd);
  }
});

//Add pref to rd.api.
rd.api.addMethod("pref", rd.api, "pref", "id");