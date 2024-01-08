# -*- coding: utf-8 -*-

import logging
import pprint
import requests

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
        vals = {
            'csrf_token': payment_response.get('reqid'),
            'url': 'https://sampath.paycorp.lk/webinterface/qw/confirm',
            'auth_token': provider_id.sampath_auth_token,
            'client_ref': payment_response.get('clientRef')
        }
        confirm_url = '{url}?csrfToken={csrf_token}&authToken={auth_Token}&clientRef={client_ref}'.format(
            url=vals['url'],
            csrf_token=vals['csrf_token'],
            auth_Token=vals['auth_token'],
            client_ref=vals['client_ref']
        )
        confirm_response = requests.post(confirm_url, {})
        return confirm_response

    def _get_json_data_from_confirm_response(self, confirm_response):
        """
        @private - extract relevant data from confirm_data
        """
        status_code = confirm_response.status_code
        if status_code != 200:
            return {'status_code': status_code}
        response_text = confirm_response.text
        parsed_data = parse_qs(response_text, keep_blank_values=True)
        data = {key: False if value[0] == "null" else value[0] if len(value) == 1 else value for key, value in parsed_data.items()}
        data.update({"status_code": status_code})
        return data

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
        confirm_response = self._confirm_sampath_transaction(raw_data)

        _logger.info("handling redirection from Sampath with data:\n%s", pprint.pformat(raw_data))
        data = self._get_json_data_from_confirm_response(confirm_response)
        _logger.info("Processing transaction with data:\n%s", pprint.pformat(data))

        # Check the integrity of the notification
        tx_sudo = request.env['payment.transaction'].sudo()._get_tx_from_notification_data(
            'sampath', data
        )

        # Handle the notification data
        tx_sudo._handle_notification_data('sampath', data)
        return request.redirect('/payment/status')
