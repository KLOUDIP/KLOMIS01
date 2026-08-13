# -*- coding: utf-8 -*-
import uuid
import logging
import pprint
import requests
from datetime import datetime

from urllib.parse import parse_qs

from odoo import http, SUPERUSER_ID
from odoo.http import request

_logger = logging.getLogger(__name__)


class SampathController(http.Controller):
    _return_url = '/payment/sampath/return'
    _webhook_url = '/payment/sampath/webhook'

    def _confirm_sampath_transaction(self, payment_response):
        """
        @private - confirm the transaction with response data
        """
        provider_id = request.env['payment.provider'].with_user(SUPERUSER_ID).search([('code', '=', 'sampath')], limit=1)
        # random_uuid = uuid.uuid4()
        tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data('sampath', payment_response)
        if tx_sudo:
            uuid = tx_sudo.provider_reference
        else:
            uuid = ''

        values = {
            "version": "1.5",
            "operation": "PAYMENT_COMPLETE",
            "msgId": uuid,
            "requestDate": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f%z"),
            "validateOnly": False,
            "requestData": {
                "clientId": provider_id.sampath_client_id,
                "reqid": payment_response.get('reqid')
            }
        }

        confirm_response = provider_id._sampath_make_request(values)
        return confirm_response

    @http.route(_return_url, type='http', auth='public', methods=['POST', 'GET'], csrf=False, save_session=False)
    def sampath_return_from_checkout(self, **raw_data):
        """ Process the notification data sent by Sampath after redirection from checkout.

        The route is flagged with `save_session=False` to prevent Odoo from assigning a new session
        to the user if they are redirected to this route with a POST request. Indeed, as the session
        cookie is created without a `SameSite` attribute, some browsers that don't implement the
        recommended default `SameSite=Lax` behavior will not include the cookie in the redirection
        request from the payment provider to Odoo. As the redirection to the '/payment/status' page
        will satisfy any specification of the `SameSite` attribute, the session of the user will be
        retrieved and with it the transaction which will be immediately post-processed.

        :param dict raw_data: The un-formatted notification data
        """
        tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data('sampath', raw_data)
        _logger.info("handling redirection from Sampath with data:\n%s", pprint.pformat(raw_data))

        confirm_response = self._confirm_sampath_transaction(raw_data)
        _logger.info("Processing transaction with data:\n%s", pprint.pformat(confirm_response))

        tx_sudo._handle_notification_data('sampath', confirm_response)
        return request.redirect('/payment/status')