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

dojo.provide("rd.api.message");

dojo.require("rd.api");
dojo.require("rd.api.identity");

rd.api.message = {
  /**
   * @private
   * fetches a message based on a message ID.
   *
   * @param {dojo.Deferred} dfd The deferred that should be called
   * with the results.
   *
   * @param {Object} args arguments to pass to the couch calls.
   * 
   * @param {Array} ids an array of message IDs to fetch.
   */
  _fetch: function(dfd, args, ids) {
    //Generate proper key for megaview lookup.
    var keys = [];
    for (var i = 0, id; id = ids[i]; i++) {
      keys.push(['rd.core.content', 'key', id]);
    }

    rd.api().megaview({
      keys: keys,
      include_docs: true,
      reduce: false
    })
    .ok(this, function(json) {
      if(!json.rows.length) {
        dfd.errback(new Error("no message with IDs: " + ids));
      } else {
        var messageResults = [],
            bag = {},
            fromMap = {},
            fromIds = [];

        for (var i = 0, row, doc; ((row = json.rows[i]) && (doc = row.doc)); i++) {
          //Make sure we have the right aggregate to use for this row.
          var rdKey = doc.rd_key;
          var schemaId = doc.rd_schema_id;

          //Skip some schemas since it is extra stuff we do not need.
          //Prefer a blacklist vs. a whitelist, since user extensions may add
          //other things, and do not want to have extensions register extra stuff? TODO.
          if (schemaId.indexOf("/rfc822") == -1 && schemaId.indexOf("/raw") == -1) {
            // TODO: note that we may get many of the same schema, which implies
            // we need to aggregate them - tags is a good example.  For
            // now just make noise...
            if (bag[schemaId]) {
              console.warn("message", doc.rd_key, "has multiple", schemaId, "schemas");
            }
            // for now it gets clobbered if it exists...
            bag[schemaId] = row.doc;
          }

          //See if all schemas are loaded for a message bag by checking the next
          //document in the json results to see if it has a different rd_key.
          //If so, then tell any extensions about new message load.
          var nextDoc = json.rows[i + 1] && json.rows[i + 1].doc;
          if (!nextDoc || rdKey[1] != nextDoc.rd_key[1]) {
            //Have a final bag. Make sure it is not a ghost by checking
            //for a body.
            var from = bag["rd.msg.body"] && bag["rd.msg.body"].from;
            if (from) {              
              //Hold on to the from names to check if they are known later
              //TODO: this should probably be a back end extension.
              var fromId = from.join(",");
              var fromList = fromMap[fromId];
              if (!fromList) {
                fromList = fromMap[fromId] = [];
                fromIds.push(from);
              }
              fromList.push(bag);
            }

            if (bag["rd.msg.body"]) {
              messageResults.push(bag);
            }

            //Reset the bag.
            bag = {};
          }
        }

        //Look up the IDs for the from identities. If they are real
        //identities, synthesize a schema to represent this.
        //TODO: this should probably be a back-end extension.
        rd.api().contactIdentity({
          ids: fromIds
        })
        .ok(this, function(identities) {
          //Cycle through the identities, and work up a schema for
          //them if they are known.
          for (var i = 0, idty; idty = identities[i]; i++) {
            var msgBags = fromMap[idty.rd_key[1].join(",")];
            for (var j = 0, bag; bag = msgBags[j]; j++) {
              bag["rd.msg.ui.known"] = {
                rd_schema_id : "rd.msg.ui.known"
              };
            }
          }

          dfd.callback(messageResults);
        })
        .error(dfd);
      }
    })
    .error(dfd);
  },

  /**
   * @private
   * filters out messages that are not "fresh" -- messages that have not been
   * deleted or archived.
   *
   * @param {dojo.Deferred} dfd The deferred that should be called
   * with the results.
   *
   * @param {Object} args arguments to pass to the couch calls.
   * 
   * @param {Array} ids an array of items with an rd_key that is for a message.
   */
  _fresh: function(dfd, args, ids) {
    //Get the key for each item and build up a quick lookup that has all
    var fresh = {}, keys = [];
    for (var i = 0, id; id = ids[i]; i++) {
      keys.push(["rd.core.content", "key-schema_id", [id.rd_key, "rd.msg.archived"]]);
      keys.push(["rd.core.content", "key-schema_id", [id.rd_key, "rd.msg.deleted"]]);
      fresh[id.rd_key.join(",")] = true;
    }

    rd.api().megaview({
      keys: keys,
      reduce: false,
      include_docs: true
    })
    .ok(function(json) {
      //For anything seen/deleted/archived, mark it as not fresh.
      for (var i = 0, row, doc; (row = json.rows[i]) && (doc = row.doc); i++) {
        var key = doc.rd_key.join(",");
        if (doc.deleted || doc.archived) {
          fresh[key] = false;
        }
      }

      //Now weed out the not-fresh from the result.
      var ret = [];
      for (var i = 0, item; item = ids[i]; i++) {
        if (fresh[item.rd_key.join(",")]) {
          ret.push(item);
        }
      }

      dfd.callback(ret);
    })
    .error(dfd);
  },

  /**
   * @private
   * Marks the rd.msg.seen as seen: true if it is not already true.
   *
   * @param {dojo.Deferred} dfd The deferred that should be called
   * with the results.
   *
   * @param {Object} args arguments to pass to the couch calls.
   * 
   * @param {Array} ids an array of message bags that have an "rd.msg.seen" property.
   */
  _seen: function(dfd, args, ids) {
    //Build up a list of docs to update.
    var updates = [];
    var api = rd.api();
    for (var i = 0, msgBag; msgBag = ids[i]; i++) {
      var seen = msgBag["rd.msg.seen"];
      if (!seen) {
        //Choose the first schema to get the rd_ values.
        for (var prop in msgBag) {
          var rdDoc = msgBag[prop];
          break;
        }
        seen = api.newDoc({
          rd_key: rdDoc.rd_key,
          rd_schema_id: "rd.msg.seen",
          rd_source: rdDoc.rd_source,
          outgoing_state: "outgoing",
          seen: false
        });

        //Update message bag with new schema.
        msgBag["rd.msg.seen"] = seen;
      }
      if (!seen.seen) {
        seen.seen = true;
        seen.outgoing_state = "outgoing";
        updates.push(seen);
      }
    }

    //Now update the docs.
    if (updates.length) {
      return rd.api().bulkUpdate({
        docs: updates
      })
      .ok(function(rows) {
        //Update the _rev for the updated values, so that the
        //client state is consistent with the server state.
        for (var i = 0, row, update; (row = rows[i]) && (update = updates[i]); i++) {
          if (update._id == row._id && row.rev) {
            update._rev = row.rev;
          }
        }
        dfd.callback(ids);
      })
      .error(dfd);
    } else {
      return this;
    }
  },

  /**
   * @private
   * Marks a schema with propName: true if it is not already true.
   *
   * @param {String} schemaId the schema ID, like "rd.msg.seen"
   *
   * @param {String} propName The property to set to true, like "seen".
   *
   * @param {Function} onEnd function to run when finished. Function will be passed
   * dfd, args, ids. onEnd function must call the deferred callbacks to finish the
   * operation.
   *
   * @param {dojo.Deferred} dfd The deferred that should be called
   * with the results.
   *
   * @param {Object} args arguments to pass to the couch calls.
   * 
   * @param {Array} ids an array of message bags that have an "rd.msg.seen" property.
   */

  _schemaTrue: function(schemaId, propName, onEnd, dfd, args, ids) {
    //Build up a list of docs to update.
    var updates = [];
    var api = rd.api();
    for (var i = 0, msgBag; msgBag = ids[i]; i++) {
      var schema = msgBag[schemaId];
      if (!schema) {
        var rdDoc = msgBag["rd.msg.body"];
        if (!rdDoc) {
          //Choose the first schema to get the rd_ values.
          for (var prop in msgBag) {
            rdDoc = msgBag[prop];
            break;
          }
        }
        schema = api.newDoc({
          rd_key: rdDoc.rd_key,
          rd_schema_id: schemaId,
          rd_source: rdDoc.rd_source,
          outgoing_state: "outgoing"
        });

        schema[propName] = false;

        //Update message bag with new schema.
        msgBag[schemaId] = schema;
      }
      if (!schema[propName]) {
        schema[propName] = true;
        schema.outgoing_state = "outgoing";
        updates.push(schema);
      }
    }

    //Now update the docs.
    if (updates.length) {
      return rd.api().bulkUpdate({
        docs: updates
      })
      .ok(function(rows) {
        //Update the _rev for the updated values, so that the
        //client state is consistent with the server state.
        for (var i = 0, row, update; (row = rows[i]) && (update = updates[i]); i++) {
          if (update._id == row._id && row.rev) {
            update._rev = row.rev;
          }
        }
        if (onEnd) {
          onEnd(dfd, args, ids);
        } else {
          dfd.callback(ids);
        }
      })
      .error(dfd);
    } else {
      dfd.callback(ids);
      return this;
    }
  }
};

dojo._mixin(rd.api.message, {
  _seen: dojo.hitch(rd.api.message, "_schemaTrue", "rd.msg.seen", "seen", null),
  _archive: dojo.hitch(rd.api.message, "_schemaTrue", "rd.msg.archived", "archived", function(dfd, args, ids) {
    rd.api().seen({
      ids: ids
    })
    .ok(dfd)
    .error(dfd);
  }),
  _del: dojo.hitch(rd.api.message, "_schemaTrue", "rd.msg.deleted", "deleted", null)
});

rd.api.extend({
  /**
   * @lends rd.api
   * Loads a set of messages. It will use the previous call's results,
   * or, optionally pass an args.ids which is an array of message IDs.
   */
  message: function(args) {
    if (args && args.ids) {
      rd.api.message._fetch(this._deferred, args, args.ids);
    } else {
      this.addParentCallback(dojo.hitch(rd.api.message, "_fetch", this._deferred, args));
    }
    return this;
  },

  /**
   * @lends rd.api
   * Only return messages that have not been deleted or archived.
   * It will use the previous call's results, or, optionally pass an args.ids
   * which is an array of items with an rd_key field.
   */
  fresh: function(args) {
    if (args && args.ids) {
      rd.api.message._fresh(this._deferred, args, args.ids);
    } else {
      this.addParentCallback(dojo.hitch(rd.api.message, "_fresh", this._deferred, args));
    }
    return this;
  },

  /**
   * @lends rd.api
   * Marks the rd.msg.seen as seen: true if it is not already true.
   * It will use the previous call's results, or, optionally pass an args.ids
   * which is an array of message bags
   * that have an "rd.msg.seen" property.
   */
  seen: function(args) {
    if (args && args.ids) {
      rd.api.message._seen(this._deferred, args, args.ids);
    } else {
      this.addParentCallback(dojo.hitch(rd.api.message, "_seen", this._deferred, args));
    }
    return this;
  },

  /**
   * @lends rd.api
   * Marks the messages as archived if by setting an rd.msg.archive schema on it.
   * Allow will call seen() for all messages archived.
   * It will use the previous call's results, or, optionally pass an args.ids
   * which is an array of message bags.
   */
  archive: function(args) {
    if (args && args.ids) {
      rd.api.message._archive(this._deferred, args, args.ids);
    } else {
      this.addParentCallback(dojo.hitch(rd.api.message, "_archive", this._deferred, args));
    }
    return this;
  },

  /**
   * @lends rd.api
   * Marks the messages as deleted by setting a rd.msg.deleted schema on it.
   * It will use the previous call's results, or, optionally pass an args.ids
   * which is an array of message bags.
   */
  del: function(args) {
    if (args && args.ids) {
      rd.api.message._del(this._deferred, args, args.ids);
    } else {
      this.addParentCallback(dojo.hitch(rd.api.message, "_del", this._deferred, args));
    }
    return this;
  }
});
