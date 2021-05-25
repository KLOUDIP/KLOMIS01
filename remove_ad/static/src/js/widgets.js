odoo.define('remove_ad.document_signing_extend', function(require) {
    'use strict';

    var core = require('web.core');
    var document_signing = require('sign.document_signing');

    var _t = core._t;

    document_signing.ThankYouDialog.include({
        template: "sign.no_pub_thank_you_dialog",
        init: function(parent, RedirectURL, RedirectURLText, requestID, options) {
            options = (options || {});
            options.title = options.title || _t("Thank You !");
            options.subtitle = options.subtitle || _t("Your signature has been saved.");
            options.size = options.size || "medium";
            options.technical = false;
            options.buttons = [];
            this.RedirectURL = RedirectURL;
            this.RedirectURLText = RedirectURLText;
            this.requestID = requestID;
            this._super(parent, options);

            this.on('closed', this, this.on_closed);
        },
        on_closed: function () {
            window.location.reload();
        },
    });
});