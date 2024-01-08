# -*- coding: utf-8 -*-

import logging

from werkzeug import urls

from odoo import _, api, models, SUPERUSER_ID
from odoo.exceptions import ValidationError

from odoo.addons.payment_sampath.const import STATUS_CODES_MAPPING
from odoo.addons.payment_sampath.controllers.main import SampathController

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _get_processing_values(self):
        """
        @Override - adding necessary values for sampath payment
        """
        res = super()._get_processing_values()
        if self.provider_code != 'sampath':
            return res
        return_url = urls.url_join(self.provider_id.get_base_url(), SampathController._return_url)
        res.update({
            'sampath_client_id': int(self.provider_id.sampath_client_id),  # This value should be number format, so converted to integer
            'sampath_client_ref': res.get('reference', ''),
            'sampath_currency': self.env['res.currency'].with_user(SUPERUSER_ID).browse(res.get('currency_id', False)).name,  # TODO Enable when production
            # 'sampath_currency': 'LKR',
            'sampath_return_url': return_url,
            'sampath_amount': res.get('amount', 0.00) * 100,  # Amount must be in cents  # TODO: Enable when production
            # 'sampath_amount': 1010,
        })
        return res

    def _get_tx_from_notification_data(self, provider_code, notification_data):
        """ Override of payment to find the transaction based on Sampath data.

        :param str provider_code: The code of the provider that handled the transaction
        :param dict notification_data: The normalized notification data sent by the provider
        :return: The transaction if found
        :rtype: recordset of `payment.transaction`
        :raise: ValidationError if the data match no transaction
        """
        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'sampath' or len(tx) == 1:
            return tx

        reference = notification_data.get('clientRef', False)
        if reference:
            tx = self.search([('reference', '=', reference), ('provider_code', '=', 'sampath')])
            if not tx:
                raise ValidationError("Sampath: " + _("No transaction found matching reference %s.", reference))
        else:  # FIXME: Handle status code 500
            error = 'Unknown error occurred when processing the transaction with Sampath (Payment Already confirmed ' \
                    'with bank but not with our system please contact our hotline)'
            _logger.warning(error)
            raise ValidationError(error)

        return tx

    def _process_notification_data(self, notification_data):
        """ Override of payment to process the transaction based on Sampath data.

        Note: self.ensure_one()

        :param dict notification_data: The normalized notification data sent by the provider
        :return: None
        :raise: ValidationError if inconsistent data were received
        """
        super()._process_notification_data(notification_data)
        if self.provider_code != 'sampath':
            return

        status_code = int(notification_data.get('status_code', False))
        if status_code in STATUS_CODES_MAPPING['pending']:
            self._set_pending()
        elif status_code in STATUS_CODES_MAPPING['done']:
            self._set_done()
        elif status_code in STATUS_CODES_MAPPING['cancel']:
            self._set_canceled()
        elif status_code in STATUS_CODES_MAPPING['refused']:
            self._set_error(_("Your payment was refused (code %s). Please try again.", status_code))
        elif status_code in STATUS_CODES_MAPPING['error']:
            self._set_error(_(
                "An error occurred during processing of your payment (code %s). Please try again.",
                status_code,
            ))
        else:
            _logger.warning(
                "received data with invalid payment status (%s) for transaction with reference %s",
                status_code, self.reference
            )
            self._set_error("Sampath: " + _("Unknown status code: %s", status_code))
