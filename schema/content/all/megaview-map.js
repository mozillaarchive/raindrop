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

function(doc) {
  if (doc.rd_schema_id
    && !doc.rd_megaview_ignore_doc) {
    // (almost) every row we emit for this doc uses an identical 'value'.
    var row_val = {'_rev': doc._rev,
                   'rd_key' : doc.rd_key,
                   'rd_schema_id' : doc.rd_schema_id
                  }
    // first emit some core 'pseudo-schemas'.
    emit(['key', doc.rd_key], row_val);
    emit(['schema_id', doc.rd_schema_id], row_val);
    emit(['key-schema_id', [doc.rd_key, doc.rd_schema_id]], row_val);

    // There may be multiple of the same schema for different extensions
    // in a single doc.  While we don't emit the individual values, we do emit
    // rd.core.content records which indicate they exist.
    for (var rd_ext_id in doc.rd_schema_items) {
      var schema_item = doc.rd_schema_items[rd_ext_id]
      var si_row_val = {'_rev': doc._rev,
                        'rd_key' : doc.rd_key,
                        'rd_schema_id' : doc.rd_schema_id,
                        'rd_ext_id': rd_ext_id,
                        'rd_source': schema_item.rd_source
                        };
      emit(['ext_id', rd_ext_id], si_row_val);
      // don't emit the revision from the source in the key.
      var src_val;
      if (schema_item.rd_source)
        src_val = schema_item.rd_source[0];
      else
        src_val = null;

      emit(['source', src_val], si_row_val);
      emit(['ext_id-source', [rd_ext_id, src_val]], si_row_val);
      // Emit any extra dependencies
      if (schema_item.rd_deps) {
        for (var i=0; i<schema_item.rd_deps.length; i++) {
          emit(['dep', schema_item.rd_deps[i]], si_row_val);
        }
      }
    }
  }
}
