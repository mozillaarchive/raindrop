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

/*jslint nomen: false, plusplus: false */
/*global require: false */
"use strict";

require.def("rdw/Message",
["require", "rd", "dojo", "rdw/_Base", "rd/friendly", "rd/hyperlink",
 "rd/api", "rdw/Attachments", "text!rdw/templates/Message.html", "text!rdw/templates/MessagePhotoAttach.html"], function (
  require,   rd,   dojo,   Base,        friendly,      hyperlink,
  api,      Attachments,       template,                          photoAttachTemplate) {

    return dojo.declare("rdw.Message", [Base], {
        //Suggested values for type are "topic" and "reply"
        type: "topic",
    
        //Allows the message to have focus.
        tabIndex: 0,

        //Holds the aggregated message object.
        //Warning: this is a prototype property: be sure to
        //set it per instance.
        msg: null,

        //Widget used to show attachments. Only created if an attachment
        //is added by an extension.
        attachmentWidget: "rdw/Attachments",

        photoAttachTemplate: photoAttachTemplate,

        //Extension point for link attachment handlers. An extension that can
        //handle link attachments should register a schema and handler function
        // with this object..
        //This array is on the object's prototype, so it applies to all
        //instances of rdw/Message.
        linkHandlers: [],

        defaultLinkHandler: function () {return true;},

        templateString: template,

        //The link for the expanding to full conversation.
        expandLink: "",

        /** Dijit lifecycle method, before template is generated */
        postMixInProperties: function () {
            this.inherited("postMixInProperties", arguments);
    
            //Set the properties for this widget based on msg
            //properties.
            var schemas = this.msg.schemas,
                bodySchema = schemas['rd.msg.body'],
                fTime, known;
    
            this.fromId = (bodySchema.from && bodySchema.from[1]) || "";
            this.fromName = bodySchema.from_display || this.fromId;
            this.subject = hyperlink.add(rd.escapeHtml(this.conversation.subject || ""));
    
            //TODO: make message transforms extensionized.
            this.message = hyperlink.add(rd.escapeHtml(bodySchema.body_preview));
    
            this.time = bodySchema.timestamp;
    
            /* XXX this timestamp needs a lot more thought to show the right kind of 
                 time info and we probably also want to some standard the hCard formatting */
            fTime = friendly.timestamp(bodySchema.timestamp);
            this.utcTime = fTime.utc;
            this.localeTime = fTime.locale;
            this.friendlyTime = fTime.friendly;
            this.additionalTime = fTime.additional;
    
            //Determine if the sender is known and switch templates if necessary.
            known = !!schemas["rd.msg.ui.known"];
            if (!known && this.fromNode) {
                //This identity is unknown. Try to make a suggestion for who it might be.
                dojo.addClass(this.fromNode, "unknown");
            }
    
            //Set up the link for the full conversation view action.
            this.convoId = schemas &&
                           schemas["rd.msg.conversation"] &&
                           schemas["rd.msg.conversation"].conversation_id;
            if (this.convoId) {
                this.expandLink = "rd:conversation:" + dojo.toJson(this.convoId);
            }
        },

        /** Dijit lifecycle method, after template in DOM */
        postCreate: function () {
            this.inherited("postCreate", arguments);

            var bodySchema = this.msg.schemas['rd.msg.body'],
                msgKey = this.msg.id,
                attachments = this.msg.attachments;

            //Set up attachments, if an attachment widget is configured.
            if (this.attachmentWidget && attachments) {
                // Build a list of our explicit handlers + default handlers.
                var allHandlers = this.linkHandlers.slice();
                allHandlers.push({schemas: ['rd.attach.link'],
                                  handler: this.defaultLinkHandler});
                allHandlers.push({schemas: ['rd.attach.file', 'rd.attach.thumbnail'],
                                  handler: this.defaultFileHandler});
                
                // Determine the schemas we need for attachments and links. We
                // want the union of all schemas for all attachments, and the
                // "handled" schemas
                var wantedSchemasSet = {};
                rd.iter(allHandlers, function (lh) {
                    rd.iter(lh.schemas, function (sid) {
                        if (!wantedSchemasSet[sid]) {
                            rd.iter(attachments, function (attach) {
                                if (attach.schemas.hasOwnProperty(sid)) {
                                    wantedSchemasSet[sid] = true;
                                }
                            });
                        }
                    });
                });

                // turn it back into an array of unique items
                var wantedSchemas = [];
                for (var sid in wantedSchemasSet) {
                    if (wantedSchemasSet.hasOwnProperty(sid)) {
                        wantedSchemas.push(sid);
                    }
                }
                if (wantedSchemas.length) {
                    // the ids of all attachments
                    var all_ids = [];
                    rd.iter(attachments, function (attach) {
                        all_ids.push(attach.id);
                    });
                    api({
                        url: 'inflow/attachments/by_id',
                        keys: all_ids,
                        schemas: wantedSchemas
                    })
                    .ok(this, function (json) {
                        this.showAttachments(allHandlers, json);
                    });
                } else {
                    this.showAttachments([], []); 
                }
            }

            api().me().ok(this, function (idtys) {
                var myself = idtys.map(function (idty) {
                        return idty.rd_key[1][1];
                    }),
                    i, email, username, name, display, first_name,
                    emailTest = function (e) {
                        return e === email;
                    };
    
                if (bodySchema.to) {
                    for (i = 0; i < bodySchema.to.length; i++) {
                        email = bodySchema.to[i][1];
                        name = bodySchema.to_display[i];
                        if (!myself.some(emailTest)) {
                            username = email.slice(0, email.indexOf("@"));
                            //XXX hacky first name grabber, will also grab titles like "Mr."
                            first_name = bodySchema.to_display[i].split(" ")[0];
                            display = first_name || username;
                            dojo.create("li", { "class" : "recipient to", "innerHTML" : display, "title" : name + " <" + email + ">" }, this.toRecipientsNode);
                        } else {
                            // more addresses than just me in the to or just me and others cc'd
                            if (bodySchema.to.length > 1 || (bodySchema.cc && bodySchema.cc.length > 0)) {
                                // XXX l10n that "me" string
                                dojo.create("li", { "class" : "recipient to", "innerHTML" : "me", "title" : name + " <" + email + ">" }, this.toRecipientsNode);
                            }
                        }
                    }
                }
    
                if (bodySchema.cc) {
                    for (i = 0; i < bodySchema.cc.length; i++) {
                        email = bodySchema.cc[i][1];
                        name = bodySchema.cc_display[i];
                        if (!myself.some(emailTest)) {
                            username = email.slice(0, email.indexOf("@"));
                            //XXX hacky first name grabber, will aslo grab titles like "Mr."
                            first_name = bodySchema.cc_display[i].split(" ")[0];
                            display = first_name || username;
                            dojo.create("li", { "class" : "recipient cc", "innerHTML" : display, "title" : name + " <" + email + ">" }, this.ccRecipientsNode);
                        } else {
                            // more than just me in the cc or other addresses in the to
                            if (bodySchema.cc.length > 1 || (bodySchema.to && bodySchema.to.length > 0)) {
                                // XXX l10n that "me" string
                                dojo.create("li", { "class" : "recipient to", "innerHTML" : "me", "title" : name + " <" + email + ">" }, this.ccRecipientsNode);
                            }
                        }
                    }
                }
            });
        },

        /**
         * A callback for extensions that adding attachments.
         * @param {String} html: the HTML for showing the attachment.
         * @param {String} type the type of attachment. Either "link" or "file".
         */
        addAttachment: function (html, type) {
            //Only create an attachment widget if attachments will be shown.
            if (this.attachmentNode) {
                if (!this.attachments) {
                    this.attachments = new (require(this.attachmentWidget))({
                    }, this.attachmentNode);
                }
                this.attachments.add(html, type);
            }
        },


        /**
         * Shows the attachments by creating an attachment widget. Should
         * be called after fetching any file attachment metadata.
         */
        showAttachments: function (handlers, attachments) {
            rd.iter(attachments, dojo.hitch(this, function (attach) {
                var handled = false;
                rd.iter(handlers, dojo.hitch(this, function (handler) {
                    // We only check the first schema ID for the handler; the
                    // other schemas are 'supplementary' schemas.
                    for (var sid in attach.schemas) {
                        if (sid==handler.schemas[0] && handler.handler.call(this, attach)) {
                            handled = true;
                            break;
                        }
                    }
                    if (handled) {
                        return false;
                    }
                    return true;
                }))
            }));
            //Render attachments, if they exist.
            if (this.attachments) {
                this.attachments.display();
            }
        },

        /**
         * Handles displaying each file attachment.
         * @param {Object} file json object for a file attachment,
         * from the inflow/message/attachments API
         */
        defaultFileHandler: function (attachment) {
            var schemas = attachment.schemas,
                bodySchema = this.msg.schemas["rd.msg.body"],
                thumb = schemas["rd.attach.thumbnail"],
                details = schemas["rd.attach.file"],
                html;

            if (thumb) {
                html = rd.template(this.photoAttachTemplate, {
                    extraClass: "",
                    imgUrl: thumb.url,
                    imgClass: "",
                    href: details.url,
                    title: details.name || "",
                    userName: bodySchema.from[1] || "",
                    realName: bodySchema.fromDisplay || "",
                    description: details.content_type
                });
            } else {
                html = '<div class="file"><a target="_blank" href="' +
                        details.url + '">' + (details.name || details.content_type) + '</a></div>';
            }

            this.addAttachment(html, "file");
            return true;
        },

        /**
         * handles clicks. Uses event
         * delegation to publish the right action.
         * @param {Event} evt
         */
        onClick: function (evt) {
            var target = evt.target,
                href = target.href;
            if (href && (href = href.split("#")[1])) {
                if (href === "quote") {
                    if (dojo.hasClass(target, "collapsed")) {
                        rd.escapeHtml(this.i18n.hideQuotedText, target, "only");
                        dojo.query(target).next(".quote").style({
                            display: "block"
                        });
                        dojo.removeClass(target, "collapsed");
                    } else {
                        rd.escapeHtml(this.i18n.showQuotedText, target, "only");
                        dojo.query(target).next(".quote").style({
                            display: "none"
                        });
                        dojo.addClass(target, "collapsed");                    
                    }
                    dojo.stopEvent(evt);
                }
            }
        },

        formatQuotedBody: function () {
            //Looks at the rd.msg.body.quoted schema for quoted blocks and formats them.
            //If no rd.msg.body.quoted exists, the message body will be used.
            var quoted = this.msg.schemas["rd.msg.body.quoted"],
                text, parts, i, part;

            //No quoted, fallback to body text.
            if (!quoted) {
                text = this.prepBodyPart(this.msg.schemas["rd.msg.body"].body);
            } else {
                parts = quoted.parts || [];
                text = "";
                for (i = 0; (part = parts[i]); i++) {
                    if (part.type === "quote") {
                        //Add in a collapsible wrapper around the text.
                        //The awkward use of single quotes for attributes is to
                        //get around encoding issue with dijit.
                        text += "<a href='#quote' class='quoteToggle collapsed'>" + this.i18n.showQuotedText + "</a>" +
                                "<div class='quote' style='display: none'>" +
                                this.prepBodyPart(part.text) +
                                "</div>";
                    } else {
                        text += this.prepBodyPart(part.text);
                    }
                }
            }

            return text;
        },

        /**
         * Does final formatting of a body part for display, HTML sanitation/transforms.
         * @param {String} text
         */
        prepBodyPart: function (text) {
            //TODO: make this extensible, or pull out hyperlinking as an extension?
            return hyperlink.add(rd.escapeHtml(text).replace(/\n/g, "<br>"));
        }
    });
});
