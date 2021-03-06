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

import re

collapseRegExp = re.compile("\n(?!>)")
startRegExp = re.compile("\n>")
linefeeds = re.compile('\r')

# Creates 'rd.msg.body.quoted' schemas for messages...
def handler(doc):
    text = doc['body']

    #Ignore messages with no body.
    if not text:
        return
    
    #Remove \r to make processing easier.
    text = linefeeds.sub('', text)

    startIndex = 0;
    oldIndex = 0;
    ret = []
    startMatch = startRegExp.search(text, startIndex)
    while startMatch and startMatch.start() != -1:
        startIndex = startMatch.start()
        #output the unquoted text
        ret.append({
            "text": text[oldIndex:startIndex]
        })

        #Find the end block and write that out.
        matches = collapseRegExp.search(text, startIndex)
        if matches:
          position = matches.end()
        else:
          #No match, so quote must be to the end of the string.
          position = len(text)

        ret.append({
            "text": text[startIndex:position],
            "type": "quote"
        })

        #Increment position in the string.
        oldIndex = startIndex = position
        startMatch = startRegExp.search(text, startIndex)

    #Add any trailing unqouted text.
    length = len(text)
    if oldIndex < length:
        ret.append({
            "text": text[oldIndex:length]
        })

    emit_schema('rd.msg.body.quoted', {
        "parts": ret
    })

