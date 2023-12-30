/** @odoo-module */

import checkoutForm from 'payment.checkout_form';
import manageForm from 'payment.manage_form';


const sampathBankMixin = {

    /**
     * Redirect the customer to Sampath Bank hosted payment page.
     *
     * @override method from payment.payment_form_mixin
     * @private
     * @param {string} code - The code of the payment option
     * @param {number} paymentOptionId - The id of the payment option handling the transaction
     * @param {object} processingValues - The processing values of the transaction
     * @return {undefined}
     */
    _processRedirectPayment: function (code, paymentOptionId, processingValues) {
        if (code !== 'sampathbank') {
            return this._super(...arguments);
        }

        this._rpc({
            model: 'payment.transaction',
            method: 'get_sampathbank_payment_init_url',
            args: [processingValues.payment_transaction_id, processingValues.reference]
        }).then(paymentPageUrl => {
            // window.location.href = paymentPageUrl;
            // return;
            // window.location.replace(paymentPageUrl);
            // return;
            window.open(paymentPageUrl,'_blank');
        }).guardedCatch(error => {
            error.event.preventDefault();
            this._displayError(
                this.model.env._t("Server Error"),
                this.model.env._t("We are not able to process your payment."),
                error.message.data.message
            );
        });
    },
};

checkoutForm.include(sampathBankMixin);
manageForm.include(sampathBankMixin);