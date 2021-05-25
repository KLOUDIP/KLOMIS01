odoo.define('kloudip_web_jsi.change_logo', function(require) {
    "use strict";

    var ajax = require('web.ajax');
    var core = require('web.core');
    var HomeMenu = require('web_enterprise.HomeMenu');
    var qweb = core.qweb;
    ajax.loadXML('/kloudip_web_jsi/static/src/xml/base.xml', qweb);
})