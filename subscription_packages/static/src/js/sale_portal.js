/** @odoo-module **/

import publicWidget from "@web/legacy/js/public/public_widget";

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

    _refreshOrderUI(promises){
        window.location.reload();
    },

    /**
     * @private:
     * update the assigned sale order subscription package
     **/
    _updateSaleSubscriptionPackage(saleOrderId, subscriptionPriceId) {
        // Calling a rpc for update the sale order
        return this.rpc("/portal/update/sale/subscription/package", {
            'subscription_pkg_id': subscriptionPriceId,
            'sale_id': saleOrderId
        })
    },

    /**
     * @override: update necessary fields
     **/
    async _onChangeSubscriptionPackage(ev) {
        ev.preventDefault();
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

        let result = await self._updateSaleSubscriptionPackage(saleId, subscriptionPkgId);
        self._refreshOrderUI(result);
    },

})