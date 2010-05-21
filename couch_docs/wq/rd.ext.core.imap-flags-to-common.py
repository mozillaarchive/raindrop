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

# Takes the raw IMAP flags from an IMAP server and converts them to
# raindrop schema items which convey the same information.
# XXX - currently only '\\Seen' is supported...
from raindrop.proto.imap import get_rdkey_for_email

def handler(doc):
    # This is dealing with the 'imap folder state cache doc' - it stores
    # all meta-data about all items in a folder; so one document holds the
    # state for many messages.  We first need to determine which are
    # different...
    rdkeys = []
    imap_flags = []
    folder_name = doc['rd_key'][1][1]

    for item in doc['infos']:
        msg_id = item['ENVELOPE'][-1]
        rdkey = get_rdkey_for_email(msg_id)
        rdkeys.append(rdkey)
        imap_flags.append((rdkey, item['FLAGS']))
    result = open_view('raindrop!content!all', 'msg-seen-flag', keys=rdkeys)

    # turn the result into a dict keyed by rdkey
    couch_values = {}
    for row in result['rows']:
        couch_values[hashable_key(row['key'])] = row['value']

    # work out which of these rdkeys actually exist in our db.
    existing_rdkeys = set()
    existing = open_schemas(((rdkey, 'rd.msg.rfc822') for rdkey in rdkeys),
                            include_docs=False)
    for e, rdkey in zip(existing, rdkeys):
        if e is not None:
            existing_rdkeys.add(rdkey)

    # find what is different...
    nnew = 0
    nupdated = 0
    # Note it is fairly common to see multiples with the same msg ID in, eg
    # a 'drafts' folder, so skip duplicates to avoid conflicts.
    seen_keys = set()
    for rdkey, flags in imap_flags:
        if rdkey in seen_keys:
            logger.info('skipping duplicate message in folder %r: %r',
                        folder_name, rdkey)
            continue
        if rdkey not in existing_rdkeys:
            # this means we haven't actually sucked the message into raindrop
            # yet (eg, --max-age may have caused only a subset of the messages
            # to be grabbed, although all messages in the folder are returned
            # in the input document)
            logger.debug('skipping message not yet in folder %r: %r',
                         folder_name, rdkey)
            continue
        seen_keys.add(rdkey)
        seen_now = "\\Seen" in flags
        try:
            couch_value = couch_values[rdkey]
        except KeyError:
            # new message
            items = {'seen' : seen_now,
                     'outgoing_state' : 'incoming',
                     }
            emit_schema('rd.msg.seen', items, rdkey)
            nnew += 1
        else:
            # If the state in couch is anything other than 'incoming'', it
            # represents a request to change the state on the server (or the
            # process of trying to update the server).
            if couch_value.get('outgoing_state') != 'incoming':
                logger.info("found outgoing 'seen' state request in doc with key %r", rdkey)
                continue
            seen_couch = couch_value['seen']
            if seen_now != seen_couch:
                items = {'seen' : seen_now,
                         'outgoing_state' : 'incoming',
                         '_rev' : couch_value['_rev'],
                         }
                emit_schema('rd.msg.seen', items, rdkey)
                nupdated += 1
    logger.info("folder %r needs %d new and %d updated 'seen' records",
                folder_name, nnew, nupdated)
