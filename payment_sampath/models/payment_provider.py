# -*- coding: utf-8 -*-
import logging
import requests
import pprint
import hmac
import hashlib
import json
import uuid


from odoo import fields, models, _, api
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('sampath', "Sampath")], ondelete={'sampath': 'set default'})
    sampath_client_id = fields.Char(
        string="Sampath ClientID", required_if_provider='sampath', groups='base.group_system')
    sampath_hmac_secret = fields.Char(string="Sampath HMAC Secret", groups='base.group_system')
    sampath_auth_token = fields.Char(
        string="Auth Token", help="Auth token for confirm the transaction", required_if_provider='sampath')

    def _sampath_get_api_url(self):
        """ sampath URLS """

        if self.state == 'enabled':
            return 'https://sampath.paycorp.lk/rest/service/proxy'
        else:
            return 'https://sampath.paycorp.lk/rest/service/proxy'

    def _sampath_make_request(self, payload=None):
        """ Make a request to Sampath API at the specified endpoint.

        Note: self.ensure_one()

        :param str endpoint: The endpoint to be reached by the request.
        :param dict payload: The payload of the request.
        :param str method: The HTTP method of the request.
        :return The JSON-formatted content of the response.
        :rtype: dict
        :raise ValidationError: If an HTTP error occurs.
        """
        self.ensure_one()

        url = self._sampath_get_api_url()

        hmac_secret = self._sampath_generate_hmac(payload)

        headers = {
            'AUTHTOKEN': f'{self.sampath_auth_token}',
            'HMAC': f'{hmac_secret}',
            'Content-Type': 'application/json'
        }

        try:
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError:
                _logger.exception(
                    "Invalid API request at %s with data:\n%s", url, pprint.pformat(payload),
                )
                response_content = response.json()
                error_code = response_content.get('error')
                error_message = response_content.get('message')
                raise ValidationError("Sampath: " + _(
                    "The communication with the API failed"
                    "information: '%s' (code %s)", error_message, error_code
                ))
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            _logger.exception("Unable to reach endpoint at %s", url)
            raise ValidationError(
                "Sampath: " + _("Could not establish the connection to the API.")
            )
        return response

    def _sampath_generate_hmac(self, payload):
        HMACSecret = self.sampath_hmac_secret
        raw_payload = json.dumps(payload)
        hmac_object = hmac.new(key=HMACSecret.encode(), msg=raw_payload.encode(), digestmod=hashlib.sha256)

        HMAC = hmac_object.hexdigest()

        return HMAC
