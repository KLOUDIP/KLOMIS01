/** @odoo-module */

export class SampathOptions {
    /**
     * Prepare the options to init the Sampath JS Object.
     *
     * This method serves as a hook for modules that would fully implement Sampath Connect.
     *
     * @param {object} processingValues
     * @return {object}
     */
    _prepareSampathOptions(processingValues) {
        return  {
            clientId: processingValues.sampath_client_id,
            paymentAmount: processingValues.sampath_amount,
            currency: processingValues.sampath_currency,
            returnUrl: processingValues.sampath_return_url,
            clientRef: processingValues.sampath_client_ref,
        };
    };
}