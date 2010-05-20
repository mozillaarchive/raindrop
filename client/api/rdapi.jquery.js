/*jslint regexp: false, plusplus: false */
/*global jQuery: false, console: false */
"use strict";

//Some functions to add to jquery to make it easy to work with Raindrop API.

var rdapi;

(function ($) {
    var global = this,
        masterPattern = /\{([^\}]+)\}/g,
        empty = {},
        ostring = Object.prototype.toString,
        config = {
            baseUrl: '/raindrop/',
            apiPath: '_api/inflow/'
        };

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

    function getProp(parts, create, context) {
        var obj = context || global, i, p;
        for (i = 0; obj && (p = parts[i]); i++) {
            obj = (p in obj ? obj[p] : (create ? obj[p] = {} : undefined));
        }
        return obj; // mixed
    }

    function getObject(name, create, context) {
        return getProp(name.split("."), create, context);
    }

    function normalize(options) {
        if (typeof options === 'string') {
            options = {
                template: options
            };
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
        var injectTemplate = (this && this !== global), self = this;

        mixin(options, {
            success: function (json) {
                var template = options.template,
                    html;
                if (injectTemplate && template) {
                    json.forEach(function (item) {
                        html += rdapi.template(template, item);
                    });
                    $(html).appendTo(self);
                }

                if (options.debug) {
                    options.debug(json);
                }
            }
        });

        ajax(url, options);
    };

    rdapi.template = function (tmpl, map, pattern) {
        return tmpl.replace(pattern || masterPattern, isFunction(map) ?
            map : function (x, k) {
                return getObject(k, false, map);
            });
    };

    rdapi.config = function (cfg) {
        mixin(config, cfg, true);
    };

    $.fn.rdapi = rdapi;

}(jQuery));
