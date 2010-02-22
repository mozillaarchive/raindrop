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

# Emit rd.msg.grouping-tag schemas for emails.
def get_recips(doc):
    fr = doc.get('from')
    if fr:
        yield fr, doc.get('from_display')
    for recip, name in zip(doc.get('to', []), doc.get('to_display', [])):
        yield recip, name
    for recip, name in zip(doc.get('cc', []), doc.get('cc_display', [])):
        yield recip, name

def handler(src_doc):
    # We make our lives easier by using the rd.msg.body schema, but only
    # do emails...
    if src_doc['rd_key'][0] != 'email':
        return

    my_identities = get_my_identities()
    to = src_doc.get('to', [])
    # First check if any of the identities is marked as being 'broadcast' or
    # 'group'
    from_id = src_doc.get('from')
    bulk_sender = False
    deps = []
    if from_id:
        # We must mark the sender identity flags schema as a dependency - even
        # when it doesn't yet exist - it may be created later, at which time
        # we need to be re-executed.
        idty_rdkey = ['identity', from_id]
        deps = [(idty_rdkey, 'rd.identity.sender-flags')]
        flags_schema = open_schemas(deps)[0] # will be None if it doesn't exist
        if flags_schema is not None:
            bulk_sender = flags_schema.get('bulk')

    logger.debug('sender %s has bulk=%s', from_id, bulk_sender)

    # see if we are personally addressed.
    grouping_idid = grouping_title = None
    if not bulk_sender:
        for look_idid, look_name in get_recips(src_doc):
            if look_idid in my_identities:
                grouping_idid = look_idid
                grouping_title = look_name
                break
    if grouping_idid is None:
        # not found - create a grouping for the sender.
        grouping_idid = src_doc.get('from')
        grouping_title = src_doc.get('from_display')
    if grouping_idid:
        grouping_key = ['identity', grouping_idid]
        tag = 'identity-' + '-'.join(grouping_idid)
        init_grouping_tag(tag, grouping_key, grouping_title)
    else:
        tag = 'no-sender'

    items = {'tag' : tag}
    logger.debug('grouping tag for %r is %r', src_doc['rd_key'], tag)
    emit_schema('rd.msg.grouping-tag', items, deps=deps)
