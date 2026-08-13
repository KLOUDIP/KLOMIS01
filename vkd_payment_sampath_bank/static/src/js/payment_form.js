/** @odoo-module */

import { PaymentForm } from "@payment/js/payment_form";
import { patch } from "@web/core/utils/patch";
import { rpc, RPCError } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";

/*
 * Odoo 18/19 migration:
 * The legacy `payment.checkout_form` / `payment.manage_form` mixins (with
 * `_super`, `_rpc`, `guardedCatch`) were removed back in Odoo 17. Providers now
 * patch the `PaymentForm` OWL component and override `_processRedirectFlow`.
 *
 * NOTE: this provider's flow is non-standard (it opens the hosted payment page
 * in a new tab via a direct ORM call). Verify the rpc route/access and the
 * exact `_processRedirectFlow` signature against your v19 instance, and test
 * end-to-end with live Sampath Bank (Paycorp) credentials.
 */
patch(PaymentForm.prototype, {
    /**
     * Redirect the customer to the Sampath Bank hosted payment page.
     *
     * @override method from @payment/js/payment_form
     * @param {string} providerCode - The code of the selected payment option's provider
     * @param {number} paymentOptionId - The id of the selected payment option
     * @param {string} paymentMethodCode - The code of the selected payment method, if any
     * @param {object} processingValues - The processing values of the transaction
     * @return {void}
     */
    async _processRedirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== 'sampathbank') {
            return super._processRedirectFlow(...arguments);
        }
        try {
            const paymentPageUrl = await rpc("/web/dataset/call_kw", {
                model: "payment.transaction",
                method: "get_sampathbank_payment_init_url",
                args: [processingValues.payment_transaction_id, processingValues.reference],
                kwargs: {},
            });
            window.open(paymentPageUrl, '_blank');
        } catch (error) {
            if (error instanceof RPCError) {
                this._displayErrorDialog(
                    _t("Server Error"),
                    error.data.message || _t("We are not able to process your payment."),
                );
            } else {
                throw error;
            }
        }
    },
});
