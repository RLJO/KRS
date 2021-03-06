odoo.define('google_custom_search.search_engine', function (require) {
    'use strict';

    $(document).ready(function () {
        var ajax = require('web.ajax');
        var enginId = '';
        var enableCSE = '';
        ajax.jsonRpc("/get/engine_id/", 'call', {}).then(function (vals) {
            enginId = vals['engine_id'];
            enableCSE = vals['enable_cse'];
            if (enginId && enableCSE) {
                $('.add_cse').append('<gcse:search></gcse:search>');
                var cx = enginId;
                var gcse = document.createElement('script');
                gcse.type = 'text/javascript';
                gcse.async = true;
                gcse.src = 'https://cse.google.com/cse.js?cx=' + cx;
                var s = document.getElementsByTagName('script')[0];
                s.parentNode.insertBefore(gcse, s);
                window.onload = function () {
                    document.getElementById('gsc-i-id1').placeholder = 'Search Entire Store Here...!!!';
                };
            }
        });

    })

});