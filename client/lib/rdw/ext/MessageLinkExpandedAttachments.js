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
 * the Mozilla Foundation.
 * Portions created by the Initial Developer are Copyright (C) 2010
 * the Initial Developer. All Rights Reserved.
 *
 * Contributor(s):
 * */

/*jslint plusplus: false, nomen: false */
/*global require: false */
"use strict";

require.modify("rdw/Message", "rdw/ext/MessageLinkExpandedAttachments",
["require", "rd", "dojo", "rdw/Message"], function (
  require,   rd,   dojo,   Message) {
    /*
    Applies a display extension to rdw/Message.
    Allows showing links included in the message as inline attachments
    */

    rd.addStyle("rdw/ext/css/MessageLinkExpandedAttachments");

    rd.applyExtension("rdw/ext/MessageLinkExpandedAttachments", "rdw/Message", {
        addToPrototype: {
            linkHandlers: [{
                schemas: ["rd.attach.link.expanded"],
                handler: function (attachment) {
                    var schema = attachment.schemas["rd.attach.link.expanded"];
                    //NOTE: the "this" in this function is the instance of rdw/Message.
                    var linkNode, templateObj, template, titleTemplate;
                    template = '<a target="_blank" class="title long_url" title="${long_url}" href="${short_url}">${long_url}</a>' +
                               '<div class="description">${description}</div>' +
                               '<span class="by">by</span> ' +
                               '<abbr class="owner" title="${user_name}@${domain}">${display_name}</abbr>';

                    titleTemplate = '<a target="_blank" class="title" title="${long_url}" href="${short_url}">${title}</a>' +
                                    '<div class="description">${description}</div>' +
                                    '<span class="by">by</span> ' +
                                    '<abbr class="owner" title="${user_name}@${domain}">${display_name}</abbr>';

                    templateObj = {
                        long_url      : schema.long_url,
                        short_url     : schema.short_url,
                        domain        : schema.domain,
                        title         : schema.title || "",
                        description   : schema.description || "",
                        display_name  : schema.display_name || schema.user_name,
                        user_name     : schema.user_name || ""
                    };

                    if (schema.title) {
                        template = titleTemplate;
                    }

                    this.addAttachment('<div domain="' + schema.domain +
                                       '" class="link expanded">' +
                                       rd.template(template, templateObj) +
                                       '</div>', 'link');
                    return true;
                }
            }]
        }
    });
});
