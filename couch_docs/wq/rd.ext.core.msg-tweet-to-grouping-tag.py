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

# Emit rd.msg.grouping-tag schemas for tweets and twitter private messages.

def handler(src_doc):
    my_identities = [iid[1] for iid in get_my_identities() if iid[0]=='twitter']

    if src_doc['rd_schema_id'] == 'rd.msg.tweet.raw':
        # a normal tweet - for now, even our tweets stay in the twitter group
        if 'twitter_in_reply_to_screen_name' in src_doc and \
           src_doc['twitter_in_reply_to_screen_name'] in my_identities:
            # sent to me and others - this is targetted at the inflow.
            val = 'identity-twitter-' + src_doc['twitter_in_reply_to_screen_name']
        else:
            # look for @me in the text
            for tid in my_identities:
                if '@' + tid in src_doc.get('twitter_text', ''):
                    val = 'identity-twitter-' + tid
                    break
            else:
                # regular tweet - peek in the twitter body not aimed at me
                # (possibly even *from* me - but even they go into the twitter
                # group.)
                val = 'twitter-status-update' 
    elif src_doc['rd_schema_id'] == 'rd.msg.tweet-direct.raw':
        # direct message - it would be unusual to have a direct message not
        # targetted at one of our accounts, but you never know..
        if src_doc['twitter_sender_screen_name'] in my_identities:
            val = 'from' # XXX - wrong!
        elif src_doc.get('twitter_recipient_screen_name') in my_identities:
            val = 'identity-twitter-' + src_doc['twitter_recipient_screen_name']
        else:
            logger.info("Unusual - a direct message for %r, but we are %r",
                        src_doc.get('twitter_recipient_screen_name'), my_identities)
            val = 'twitter-status-update' # regular tweet not aimed at me...
    else:
        raise RuntimeError("Not expecting doc %r" % src_doc)
    if val is not None:
        items = {'tag': val}
        emit_schema('rd.msg.grouping-tag', items)
