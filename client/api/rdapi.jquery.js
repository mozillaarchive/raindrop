/*jslint regexp: false, plusplus: false */
/*global jQuery: false, console: false, document: false */
"use strict";

//Some functions to add to jquery to make it easy to work with Raindrop API.

var rdapi;

(function ($) {
    var global = this,
        idCounter = 0,
        masterPattern = /\{([^\}]+)\}/g,
        empty = {},
        ostring = Object.prototype.toString,
        templateRegistry = {},
        dataRegistry = {},
        dataIdCounter = 0,
        config = {
            baseUrl: '/raindrop/',
            apiPath: '_api/inflow/',
            saveTemplateData: true
        },

        //support stuff for toDom
        tagWrap = {
            option: ["select"],
            tbody: ["table"],
            thead: ["table"],
            tfoot: ["table"],
            tr: ["table", "tbody"],
            td: ["table", "tbody", "tr"],
            th: ["table", "thead", "tr"],
            legend: ["fieldset"],
            caption: ["table"],
            colgroup: ["table"],
            col: ["table", "colgroup"],
            li: ["ul"]
        },
        reTag = /<\s*([\w\:]+)/,
        masterNode = {}, masterNum = 0,
        masterName = "__ToDomId",
        param, tw;

    // generate start/end tag strings to use
    // for the injection for each special tag wrap case.
    for (param in tagWrap) {
        if (tagWrap.hasOwnProperty(param)) {
            tw = tagWrap[param];
            tw.pre  = param === "option" ? '<select multiple="multiple">' : "<" + tw.join("><") + ">";
            tw.post = "</" + tw.reverse().join("></") + ">";
            // the last line is destructive: it reverses the array,
            // but we don't care at this point
        }
    }

    function toDom(frag, doc) {
        doc = doc || document;
        var masterId = doc[masterName], match, tag, master, wrap, i, fc, df;
        if (!masterId) {
            doc[masterName] = masterId = ++masterNum + "";
            masterNode[masterId] = doc.createElement("div");
        }

        // make sure the frag is a string.
        frag += "";

        // find the starting tag, and get node wrapper
        match = frag.match(reTag);
        tag = match ? match[1].toLowerCase() : "";
        master = masterNode[masterId];

        if (match && tagWrap[tag]) {
            wrap = tagWrap[tag];
            master.innerHTML = wrap.pre + frag + wrap.post;
            for (i = wrap.length; i; --i) {
                master = master.firstChild;
            }
        } else {
            master.innerHTML = frag;
        }

        // one node shortcut => return the node itself
        if (master.childNodes.length === 1) {
            return master.removeChild(master.firstChild); // DOMNode
        }

        // return multiple nodes as a document fragment
        df = doc.createDocumentFragment();
        while ((fc = master.firstChild)) {
            df.appendChild(fc);
        }
        return df; // DOMNode
    }

    function isArray(it) {
        return ostring.call(it) === "[object Array]";
    }

    function isFunction(it) {
        return ostring.call(it) === "[object Function]";
    }

    function mixin(target, source, force) {
        for (var prop in source) {
            if (!(prop in empty) && (!(prop in target) || force)) {
                target[prop] = source[prop];
            }
        }
    }

    function getProp(parts, context) {
        var obj = context || global, i, p;
        for (i = 0; obj && (p = parts[i]); i++) {
            obj = (p in obj ? obj[p] : undefined);
        }
        return obj; // mixed
    }

    function strToInt(value) {
        return value ? parseInt(value, 10) : 0;
    }

    function getObject(name, context) {
        var brackRegExp = /\[([^\]]+)\]/,
            part = name,
            parent = context,
            match, pre, prop, obj, startIndex, endIndex, indices, result;
        
        while ((match = brackRegExp.exec(part))) {
            prop = match[1].replace(/['"]/g, "");
            pre = part.substring(0, match.index);

            part = part.substring(match.index + match[0].length, part.length);
            if (part.indexOf('.') === 0) {
                part = part.substring(1, part.length);
            }

            obj = getProp(pre.split('.'), parent);
            if (prop.indexOf(":") !== -1) {
                //An array slice action
                indices = prop.split(':');
                startIndex = strToInt(indices[0]);
                endIndex = strToInt(indices[1]);

                if (!endIndex) {
                    obj = obj.slice(startIndex);
                } else {
                    obj = obj.slice(startIndex, endIndex);
                }
            } else {
                obj = obj[prop];
            }
            parent = obj;
        }

        if (!part) {
            result = parent;
        } else {
            result = getProp(part.split("."), parent);
        }

        if (result === null || result === undefined) {
            result = '';
        }
        return result;
    }

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
            options.template = templateRegistry[options.templateId].template
        }

        return options;
    }

    function ajax(url, options) {
        options.url = config.baseUrl + config.apiPath + url;

        mixin(options, {
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

        mixin(options, {
            success: function (json) {
                var template = options.template,
                    html = '', node;
                if (options.containerNode && template) {
                    if (options.prop) {
                        json = getObject(options.prop, json);
                    }

                    if (isArray(json)) {
                        json.forEach(function (item) {
                            html += rdapi.template(template, item);
                        });
                    } else {
                        html += rdapi.template(template, json);
                    }
                    node = toDom(html);
                    if (options.node) {
                        options.containerNode.replaceChild(node, options.node);
                    } else {
                        options.containerNode.innerHTML = '';
                        options.containerNode.appendChild(node);
                    }
                    $(document).trigger('rdapi-done', options.containerNode);
                }
            }
        });

        ajax(url, options);
    };

    rdapi.template = function (tmpl, map) {
        var dataId,
            combined = tmpl.replace(masterPattern, isFunction(map) ?
                map : function (x, k) {
                    var index, templateId, prop, obj, html, result, varId;
    
                    if (k.indexOf('+') === 0) {
                        //A subtemplate. Pull of the query from the property.
                        index = k.lastIndexOf(' ');
                        templateId = k.substring(2, index);
                        prop = k.substring(index + 1, k.length);
                        obj = getObject(prop, map);
                        html = templateRegistry[templateId].template;
                        result = '';
    
                        if (!obj) {
                            console.error("cannot find property related to subtemplate: " + k);
                            return '';
                        } else if (isArray(obj)) {
                            obj.forEach(function (item) {
                                result += rdapi.template(html, item);
                            });
                            return result;
                        } else {
                            return rdapi.template(html, obj);
                        }
                    } else if (k.indexOf('!') === 0) {
                        //It is an assignment.
                        index = k.lastIndexOf(' ');
                        varId = k.substring(2, index);
                        prop = k.substring(index + 1, k.length);
                        obj = getObject(prop, map);
                        map[varId] = obj;
                        return '';
                    }

                    return getObject(k, map);
                });

        if (config.saveTemplateData && !isFunction(map)) {
            dataId = 'id' + (dataIdCounter++);
            combined = combined.replace(/<\s*\w+/, '$& data-rdapiid="' + dataId + '" ');
            dataRegistry[dataId] = map;
        }
        return combined;
    };

    rdapi.config = function (cfg) {
        mixin(config, cfg, true);
    };

    rdapi.data = function (id) {
        return dataRegistry[id];
    };

    $(function () {
        var prop, tmpl;

        //Build up lists of templates to use.
        $('.template').each(function (index, node) {
            var sNode = $(node),
                dataProp = sNode.attr('data-prop'),
                id = sNode.attr('data-id') || ('id' + (idCounter++)),
                api = sNode.attr('data-api'),
                options = sNode.attr('data-options'),
                parentNode = node.parentNode,
                textContent = '{+ ' + id + ' ' + dataProp + '}',
                textNode;

            if (options) {
                //TODO: parse the options
            }

            //Remove templating stuff from the node
            sNode.removeClass('template')
                 .removeAttr('data-id').removeAttr('data-prop')
                 .removeAttr('data-api').removeAttr('data-options');

            templateRegistry[id] = {
                prop: dataProp,
                node: node,
                api: api,
                options: options
            };

            //Replace the node with text indicating what template to use.
            var jParentNode = $(parentNode);
            if (jParentNode.hasClass('templateContainer')) {
                templateRegistry[id].containerNode = parentNode;
            } else if (jParentNode.hasClass('templateRemove')) {
                parentNode.removeChild(node);
            } else {
                textNode = document.createTextNode(textContent);
                parentNode.replaceChild(textNode, node);
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

}(jQuery));
