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

dojo.provide("rdw.ext.EXTNAME.Message");

dojo.require("rdw.Message");

dojo.declare("rdw.ext.EXTNAME.Message", [rdw.Message], {
  templateString: dojo.cache("rdw.ext.EXTNAME", "Message.html"),

  postMixInProperties: function() {
    //summary: dijit lifecycle method
    this.inherited("postMixInProperties", arguments);

    //Set any properties you want to show in the template here.
    //this.msg is the message object, with all the document schemas
    //for a message at this.msg.schemas.

    //With this.body set up, you can use ${body.subject} to print
    //out the message subject.
    this.body = this.msg.schemas['rd.msg.body'];
  }
});