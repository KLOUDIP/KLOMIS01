/** @odoo-module */
/* global Sampath */

import checkoutForm from 'payment.checkout_form';
import manageForm from 'payment.manage_form';
import { SampathOptions } from '@payment_sampath/js/sampath_options';

const sampathMixin = {

    /**
     * Redirect the customer to Sampath hosted payment page.
     *
     * @override method from payment.payment_form_mixin
     * @private
     * @param {string} code - The code of the payment option
     * @param {number} paymentOptionId - The id of the payment option handling the transaction
     * @param {object} processingValues - The processing values of the transaction
     * @return {undefined}
     */
    _processRedirectPayment: function (code, paymentOptionId, processingValues) {
        if (code !== 'sampath') {
            return this._super(...arguments);
        }

        const payLoad = new SampathOptions()._prepareSampathOptions(processingValues)
        // Redirect to sampath card details page
        loadPaycorpPayment(payLoad)
    },
};

checkoutForm.include(sampathMixin);
manageForm.include(sampathMixin);
