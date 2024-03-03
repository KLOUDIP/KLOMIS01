import logging
from urllib.parse import urljoin

from odoo import _, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment_payhere_nisus.controllers.main import PayHereController

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _get_specific_rendering_values(self, processing_values):
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'payhere_nisus':
            return res

        base_url = self.provider_id.get_base_url()
        partner_first_name, partner_last_name = payment_utils.split_partner_name(self.partner_name)

        rendering_values = {
            'merchant_id': self.provider_id.payhere_merchant_number,
            'currency': self.currency_id.name,
            'amount': self.amount,
            'order_id': self.reference,
            'notify_url': '%s' % urljoin(base_url, PayHereController._notify_url),
            'cancel_url': '%s' % urljoin(base_url, PayHereController._cancel_url),
            'return_url': '%s' % urljoin(base_url, PayHereController._return_url),
            'first_name': partner_first_name,
            'last_name': partner_last_name,
            'email': self.partner_email,
            'address': self.partner_address,
            'phone': self.partner_phone,
            'city': self.partner_city,
            'country': self.partner_country_id.name,
            'items': self.reference,
        }
        rendering_values.update({
            'api_url': self.provider_id._payhere_nisus_get_api_url(),
        })
        rendering_values['hash'] = self.provider_id._payhere_generate_sign("in", rendering_values)
        return rendering_values

    def _get_tx_from_notification_data(self, provider_code, notification_data):

        tx = super()._get_tx_from_notification_data(provider_code, notification_data)
        if provider_code != 'payhere_nisus' or len(tx) == 1:
            return tx

        reference = notification_data.get('order_id')
        if not reference:
            raise ValidationError(
                "Payhere: " + _("Received data with missing reference %(ref)s.", ref=reference)
            )

        tx = self.search([('reference', '=', reference), ('provider_code', '=', 'payhere_nisus')])
        if not tx:
            raise ValidationError(
                "Payhere: " + _("No transaction found matching reference %s.", reference)
            )

        return tx

    def _process_notification_data(self, notification_data):
        """ Override of `payment' to process the transaction based on Payhere data.

        Note: self.ensure_one()

        :param dict notification_data: The notification data sent by the provider.
        :return: None
        :raise ValidationError: If inconsistent data are received.
        """
        super()._process_notification_data(notification_data)
        if self.provider_code != 'payhere_nisus':
            return

        self.provider_reference = notification_data.get('order_id')

        status = notification_data.get('status_code')
        if not status:
            raise ValidationError("Payhere: " + _("Received data with missing payment state."))

        if status == '0':
            self._set_pending()
        elif status == '2':
            self._set_done()
        elif status in ['-1', '-3']:
            self._set_canceled()
        else:
            status_description = notification_data.get('status_message')
            _logger.info(
                "Received data with invalid payment status (%(status)s) and reason '%(reason)s' "
                "for transaction with reference %(ref)s",
                {'status': status, 'reason': status_description, 'ref': self.reference},
            )
            self._set_error("Payhere: " + _(
                "Received invalid transaction status %(status)s and reason '%(reason)s'.",
                status=status, reason=status_description
            ))
