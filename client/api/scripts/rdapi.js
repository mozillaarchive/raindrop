/*jslint */
/*global require: false, document: false, console: false */
"use strict";

require.def('rdapi', ['jquery', 'blade/object', 'blade/motif'], function ($, object, motif) {

    var rdapi,
        idCounter = 0,
        templateRegistry = {},
        idRegistry = {},
        config = {
            baseUrl: '/raindrop/',
            apiPath: '_api/inflow/',
            saveTemplateData: true
        };

    function getHtml(node) {
        var temp = document.createElement('div'),
            parent = node.parentNode,
            sibling = node.nextSibling, html;

        //Put node in temp node to get the innerHTML so node's element
        //html is in the output.
        temp.appendChild(node);
        html = temp.innerHTML;

        //move the node back.
        if (parent) {
            if (sibling) {
                parent.insertBefore(node, sibling);
            } else {
                parent.appendChild(node);
            }
        }

        return html;
    }

    function normalize(options) {
        if (typeof options === 'string') {
            options = {
                template: options
            };
        } else if (options.jquery) {
            options = {
                template: getHtml(options[0])
            };
        } else if (options.nodeType === 1) {
            options = {
                template: getHtml(options)
            };
        } else if (options.templateId) {
            options.template = templateRegistry[options.templateId].template;
        }

        //Add in functions to use in templating
        var funcs = options.funcs || (options.funcs = {});
        object.mixin(funcs, {
            'rdapi.identity': rdapi.identity,
            //TODO: make the date thing better.
            'prettyDate': function (seconds) {
                return (new Date(seconds * 1000)).toString();
            }
        })
        return options;
    }

    function ajax(url, options) {
        options.url = config.baseUrl + (url.indexOf('_design') === 0 ? '' : config.apiPath) + url;

        object.mixin(options, {
            limit: 30,
            message_limit: 3,
            dataType: 'json',
            error: function (xhr, textStatus, errorThrown) {
                console.log(errorThrown);
            }
        });

        $.ajax(options);
    }

    rdapi = function (url, options) {
        options = normalize(options);

        object.mixin(options, {
            success: function (json) {
                var template = options.template,
                    html = '', node;
                    
                //Get the identity info for any identities in the JSON
                rdapi._getIdentities(json, function () {
                    if (options.containerNode && template) {
                        if (options.prop) {
                            json = motif.getObject(options.prop, json);
                        }

                        if ($.isArray(json)) {
                            json.forEach(function (item) {
                                html += motif(template, item, options);
                            });
                        } else {
                            html += motif(template, json, options);
                        }

                        node = $(html);
                        if (options.node) {
                            $(options.node).replaceWith(node);
                        } else {
                            options.containerNode.innerHTML = '';
                            node.appendTo(options.containerNode);
                            console.log("SET THE CONTENT FOR", options.containerNode);
                        }
                        if (options.onTemplateDone) {
                            options.onTemplateDone(html);
                        }
                        $(document).trigger('rdapi-done', options.containerNode);
                    }
                });
            }
        });

        ajax(url, options);
    };

    function findIdentities(obj, found, needed) {
        var prop, schema, i, id, ids, target, idString;

        if ($.isArray(obj)) {
            for (i = 0; i < obj.length; i++) {
                findIdentities(obj[i], found, needed);
            }
            return;
        }

        if (!obj || !$.isPlainObject(obj)) {
            return;
        }

        for (prop in obj) {
            if (obj.hasOwnProperty(prop)) {
                target = obj[prop];
                if (prop === 'rd.msg.body') {
                    schema = obj[prop];
                    ids = [schema.from].concat(schema.to, schema.cc, schema.bcc);
                    for (i = 0; i < ids.length; i++) {
                        id = ids[i];
                        if (id) {
                            idString = id.toString();
                            if (!idRegistry[idString] && !found[idString]) {
                                needed.push(id);
                                found[idString] = true;
                            }
                        }
                    }
                } else if ($.isArray(target)) {
                    for (i = 0; i < target.length; i++) {
                        findIdentities(target[i], found, needed);
                    }
                } else if ($.isPlainObject(target)) {
                    findIdentities(target, found, needed);
                }
            }
        }
    }

    /**
     * Traces the json looking for nested 'rd.msg.body' schemas and if found, will
     * make sure the rd.identity schema is loaded for the identities found,
     * then call the callback.
     * @param {Object} json the json object to inspect for rd.msg.body schemas
     * @param {Function} callback the callback to execute once all the identities
     * are available.
     */
    rdapi._getIdentities = function (json, callback) {
        //Traverse the object looking for identities.
        var found = {}, needed = [], i, id, doc, row;
        findIdentities(json, found, needed);
console.log("gid1");
        if (!needed.length) {
console.log("gid2");
            callback();
        } else {
            //Build out the full key
            for (i = 0; (id = needed[i]); i++) {
                needed[i] = ["key-schema_id", [["identity", id], 'rd.identity']];
            }

            ajax('_design/raindrop!content!all/_view/megaview?reduce=false&include_docs=true', {
                type: 'POST',
                data: JSON.stringify({
                    keys: needed
                }),
                processData: false,
                success: function (json) {
                    if (json.rows.length) {
                        for (i = 0; (row = json.rows[i]); i++) {
                            doc = row.doc;
                            id = doc.rd_key[1];
                            idRegistry[id.toString()] = doc;
                        }
                    }

                    //If the asked for ids did not come back, mark them as
                    //empty schemas so that we do not ask for them again.
                    for (i = 0; (id = needed[i]); i++) {
                        id = id[1][0][1].toString();
                        id = idRegistry[id] || (idRegistry[id] = {});
                    }
                    callback();
                }
            });
        }
    };


    rdapi.config = function (cfg) {
        object.mixin(config, cfg, true);
    };

    rdapi.data = function (id) {
        return motif.data(id);
    };

    rdapi.identity = function (id) {
        return idRegistry[id.toString()] || {};
    };

    $(function () {
        var prop, tmpl;

        //Build up lists of templates to use.
        $('.template').each(function (index, node) {
            var sNode = $(node),
                dataProp = sNode.attr('data-prop'),
                id = sNode.attr('data-id') || ('id' + (idCounter++)),
                api = sNode.attr('data-api'),
                parentNode = node.parentNode,
                textContent = '{+ ' + id + ' ' + dataProp + '}',
                textNode, jParentNode;

            //Remove templating stuff from the node
            sNode.removeClass('template')
                 .removeAttr('data-id').removeAttr('data-api');

            templateRegistry[id] = {
                prop: dataProp,
                node: node,
                api: api
            };

            //Replace the node with text indicating what template to use.
            jParentNode = $(parentNode);
            if (jParentNode.hasClass('templateContainer')) {
                templateRegistry[id].containerNode = parentNode;
            } else {
                parentNode.removeChild(node);
            }
        });

        //After all template nodes have been replaced with text nodes for
        //subtemplates, now convert those nodes to be just text.
        for (prop in templateRegistry) {
            if (templateRegistry.hasOwnProperty(prop)) {
                tmpl = templateRegistry[prop];
                tmpl.template = getHtml(tmpl.node);
            }
        }

        //Finally, do all the API calls. This is a separate loop because
        //all templates need to be strings before the api calls execute in
        //case subtemplates are needed.
        for (prop in templateRegistry) {
            if (templateRegistry.hasOwnProperty(prop)) {
                tmpl = templateRegistry[prop];
                if (tmpl.api) {
                    rdapi(tmpl.api, tmpl);
                }
            }
        }

    });

    return rdapi;
});
