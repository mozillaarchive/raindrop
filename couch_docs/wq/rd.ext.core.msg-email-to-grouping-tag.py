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

# Here are our "rules".  In the following table:
# 'you', 'bulk' and 'other' are all email addresses.
# * 'you' is any one of your identities.
# * 'bulk' and 'other' are different addresses, but 'bulk' will eventually
# be flagged as a bulk sender, while 'other' is just a normal address.
#
# The first column is when raindrop first starts - the 'bulk' address has not
# yet been marked as a bulk sender.  IOW, 'bulk' and 'other' are treated the
# same.
# The second column is what happens after the user has specified 'bulk' as
# a bulk sender (other is still a 'normal' address.)
#
#Scenario                       no bulk flag          bulk flag
#-----------------------        --------              ----------
#From: you; to: bulk            you/inflow            bulk 
#From: you; to: other           you/inflow            you/inflow
#
#From: other; to: bulk          [*bulk or other]      bulk
#From: other; to: you           you/inflow            you/inflow
#From: other; to: bulk, you     you/inflow            you/inflow
#
#From: bulk ; to: other         [bulk or *other]      bulk 
#From: bulk ; to: you           you                   bulk 
#From: bulk ; to: other, you    you/inflow            bulk
#
#From: other; to: <none>        other                 other
#From: bulk ; to: <none>        bulk                  bulk

# (note - [bulk or other] means either of the 2 addresses could in theory be
# selected; they are both treated the same as neither has the 'bulk' flag yet.
# However, in both cases we choose to use the 'to' - as we aren't addressed,
# the 'to' addresses is more likely to be the actual bulk sender.

# which all reduces to:
# if sender has the bulk flag, they get it.
# if I'm personally addressed, inflow gets it.
# if any recipient has the bulk flag, they get it
# If I'm the sender, inflow gets it.
# If recipients exist, first gets it.
# Sender gets it

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

    all_recips = list(get_recips(src_doc)) # element 0 is 'from'...
    my_identities = get_my_identities()

    # get the 'bulk flags' for each recipient.  Each becomes a dependency -
    # even when it doesn't yet exist - it may be created later, at which time
    # we need to be re-executed.
    deps = [(['identity', r[0]], 'rd.identity.sender-flags') for r in all_recips]
    bulk_schemas = open_schemas(deps)
    # list of booleans corresponding to each recipient (ie, elt 0 is 'from')
    bulk_flags = [(sc or {}).get('bulk', False) for sc in bulk_schemas]

    # if sender has the bulk flag, they get it.
    if bulk_flags[0]:
        idid, title = all_recips[0]
    else:
        # if I'm personally addressed, inflow gets it.
        for rid, rtitle in all_recips[1:]:
            if rid in my_identities:
                idid = rid
                title = rtitle
                break
        else:
            # if any recipient has the bulk flag, they get it
            for (rid, rtitle), flag in zip(all_recips[1:], bulk_flags[1:]):
                if flag:
                    idid = rid
                    title = rtitle
                    break
            else:
                # If I'm the sender, inflow gets it.
                if all_recips[0][0] in my_identities:
                    idid, title = all_recips[0]
                else:
                    # If recipients exist, first gets it.
                    if len(all_recips) > 1:
                        idid, title = all_recips[1]
                    else:
                        # the sender gets it.
                        idid, title = all_recips[0]

    tag = 'identity-' + '-'.join(idid)
    init_grouping_tag(tag, ['identity', idid], title)
    items = {'tag' : tag}
    logger.debug('grouping tag for %r is %r', src_doc['rd_key'], tag)
    emit_schema('rd.msg.grouping-tag', items, deps=deps)
