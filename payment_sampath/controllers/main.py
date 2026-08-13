# -*- coding: utf-8 -*-
import logging
import pprint
from odoo import http, SUPERUSER_ID
from odoo.http import request

_logger = logging.getLogger(__name__)


class SampathController(http.Controller):
    _return_url = '/payment/sampath/return'

    def _confirm_sampath_transaction(self, payment_response):
        """ Fetch provider safely and confirm transaction """
        # Using sudo() to ensure the provider is always accessible
        provider = request.env['payment.provider'].sudo().search([('code', '=', 'sampath')], limit=1)

        tx = request.env['payment.transaction'].sudo()._get_tx_from_notification_data('sampath', payment_response)

        values = {
            "version": "1.5",
            "operation": "PAYMENT_COMPLETE",
            "msgId": tx.provider_reference or '',
            "requestDate": "...",  # Populate with current timestamp
            "validateOnly": False,
            "requestData": {
                "clientId": provider.sampath_client_id,
                "reqid": payment_response.get('reqid')
            }
        }
        return provider._sampath_make_request(values)

    @http.route(_return_url, type='http', auth='public', methods=['POST', 'GET'], csrf=False, save_session=False)
    def sampath_return_from_checkout(self, **raw_data):
        """ Secure return route """
        _logger.info("Redirected from Sampath with data: %s", pprint.pformat(raw_data))

        # Confirm transaction with Sampath API
        confirm_response = self._confirm_sampath_transaction(raw_data)

        # Process the confirmation response
        tx = request.env['payment.transaction'].sudo()._get_tx_from_notification_data('sampath', raw_data)
        tx._handle_notification_data('sampath', confirm_response)

        return request.redirect('/payment/status')
