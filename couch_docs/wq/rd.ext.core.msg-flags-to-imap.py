# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Raindrop.
#
# The Initial Developer of the Original Code is
# Mozilla Messaging, Inc..
# Portions created by the Initial Developer are Copyright (C) 2009
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#

# An extension which converts message flags to a schema processed by the
# imap protocol to reflect the new flags back to the imap server.

def handler(doc):
    # Our source schema is also written as the message is incoming, so
    # skip messages not destined to be sent.
    if doc['outgoing_state'] != 'outgoing':
        return

    # open the document with the imap-locations schema
    rdkey = doc['rd_key']
    result = open_schemas([(rdkey, 'rd.msg.imap-locations')])
    loc_doc = result[0]
    if loc_doc is None:
        logger.warning("Can't find imap location for message %r", doc['_id'])
        return

    # work out what adjustments are needed.
    if doc['rd_schema_id'] == 'rd.msg.seen':
        new_flag = '\\Seen'
        attr = 'seen'
    elif doc['rd_schema_id'] == 'rd.msg.deleted':
        new_flag = '\\Deleted'
        attr = 'deleted'
    elif doc['rd_schema_id'] == 'rd.msg.archived':
        logger.info("todo: ignoring 'archived' IMAP flag")
        return
    else:
        raise RuntimeError(doc)
    
    infos = []
    for loc_info in loc_doc['locations']:
        folder = loc_info['folder_name']
        uid = loc_info['uid']
        logger.debug("setting flags for %r: folder %r, uuid %s", rdkey, folder, uid)

        info = {'account': loc_info['account'],
                'folder': folder,
                'uid': uid,
               }
        if doc[attr]:
            info['flags_add']=[new_flag]
        else:
            info['flags_remove']=[new_flag]
        infos.append(info)
    if infos:
        si = {'locations': infos}
        emit_schema('rd.proto.outgoing.imap-flags', si)
