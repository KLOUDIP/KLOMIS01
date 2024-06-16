/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";
import { _t } from "@web/core/l10n/translation";

publicWidget.registry.SaleSubscriptionPackage = publicWidget.Widget.extend({
    selector: '.subscription_packages',
    events: {
        'change #subscription-package': '_onChangeSubscriptionPackage'
    },

    /**
     * @override: adding necessary services
     **/
    init() {
        this._super(...arguments);
        this.rpc = this.bindService("rpc");
        this.notification = this.bindService("notification");
    },

    /**
     * @private:
     * update the assigned sale order subscription package
     **/
    _updateSaleSubscriptionPackage(saleOrderId, subscriptionPriceId) {
        // Calling a rpc for update the sale order
        const self = this;
        this.rpc("/portal/update/sale/subscription/package", {
            'subscription_pkg_id': subscriptionPriceId,
            'sale_id': saleOrderId
        }).then(function (message) {
            // Add notification to notify the user
            self.notification.add(_t(message), {
                title: _t("Success"),
                type: "success",
            });
        });
    },

    /**
     * @override: update necessary fields
     **/
    _onChangeSubscriptionPackage(ev) {
        const self = this;
        // Selection field styling
        let selectElement = document.getElementById('subscription-package');
        if (selectElement.value) {
            selectElement.classList.add('selected');
        } else {
            selectElement.classList.remove('selected');
        }

        // Update prices of the products
        let saleId = $('.subscription_packages').attr('sale-id');
        let subscriptionPkgId = $('#subscription-package').val();
        let pricelists = [];
        let promises = [];

        $('.subscription_packages > table > tbody > tr').each(function(index, tr) {
            let $tr = $(tr);
            let productId = $tr.data('productid');
            let recurringLine = $tr.data('recurringline');

            let promise = self.rpc("/get/sale/subscription/package/price", {
                'sale_id': saleId,
                'subscription_package_id': subscriptionPkgId,
                'product_id': productId,
                'recurring_line_id': recurringLine,
            }).then(function (result) {
                // price unit
                let $unitPrice = $tr.find('.subscription-price-unit > strong > div');
                $unitPrice.html('<span>' + result[0] + '</span>')
                // subtotal
                let $subtotal = $tr.find('#subscription_subtotal');
                $subtotal.html('<span class="oe_order_line_price_subtotal">' + result[2] + '</span>')
                // Add pricelist status to pricelists variable
                pricelists.push(result[4])
            });

            promises.push(promise);
        });

        Promise.all(promises).then(function () {
            // Check pricelist and visible/invisible the warning
            if (pricelists.includes(false)) {
                $('.pricelist-warning').removeClass('d-none');
            } else {
                $('.pricelist-warning').addClass('d-none');
                // Update the subscription package to the sale order
                self._updateSaleSubscriptionPackage(saleId, subscriptionPkgId);
            }
        });
    },

})