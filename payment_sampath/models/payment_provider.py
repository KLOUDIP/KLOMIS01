# -*- coding: utf-8 -*-
import logging
import requests
import pprint
import hmac
import hashlib
import json

from odoo import fields, models, _
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('sampath', "Sampath")], ondelete={'sampath': 'set default'})

    sampath_client_id = fields.Char(
        string="Sampath ClientID",
        required_if_provider='sampath',
        groups='base.group_system'
    )
    sampath_hmac_secret = fields.Char(
        string="Sampath HMAC Secret",
        required_if_provider='sampath',
        groups='base.group_system'
    )
    sampath_auth_token = fields.Char(
        string="Auth Token",
        help="Auth token for confirming the transaction",
        required_if_provider='sampath',
        groups='base.group_system'
    )

    def _sampath_get_api_url(self):
        """ Return the API URL according to the provider state. """
        self.ensure_one()
        # If Sampath provides a UAT/Sandbox URL, you can return it for self.state == 'test'
        if self.state == 'enabled':
            return 'https://sampath.paycorp.lk/rest/service/proxy'
        else:
            return 'https://sampath.paycorp.lk/rest/service/proxy'

    def _sampath_make_request(self, payload=None):
        """ Make a request to Sampath API at the specified endpoint. """
        self.ensure_one()
        url = self._sampath_get_api_url()
        hmac_secret = self._sampath_generate_hmac(payload)

        headers = {
            'AUTHTOKEN': self.sampath_auth_token,
            'HMAC': hmac_secret,
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

                # Prevent JSON decoder crash if Sampath returns an HTML error (e.g. 502/504)
                try:
                    response_content = response.json()
                    error_code = response_content.get('error', 'N/A')
                    error_message = response_content.get('message', 'Unknown Error')
                except ValueError:
                    error_code = response.status_code
                    error_message = response.text

                raise ValidationError("Sampath: " + _(
                    "The communication with the API failed. Information: '%s' (code %s)", error_message, error_code
                ))

        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            _logger.exception("Unable to reach endpoint at %s", url)
            raise ValidationError(
                "Sampath: " + _("Could not establish the connection to the API.")
            )

        return response

    def _sampath_generate_hmac(self, payload):
        """ Generate HMAC for payload security """
        # Ensure the secret is present to avoid NoneType encoding errors
        if not self.sampath_hmac_secret:
            raise ValidationError(
                _("Sampath HMAC Secret is not configured. Please check your payment provider settings."))

        # Using separators ensures Python doesn't inject spaces that alter the payload hash
        raw_payload = json.dumps(payload, separators=(',', ':'))

        # UTF-8 encoding is explicitly required in Python 3.12+ to prevent byte mismatches
        hmac_object = hmac.new(
            key=self.sampath_hmac_secret.encode('utf-8'),
            msg=raw_payload.encode('utf-8'),
            digestmod=hashlib.sha256
        )

        return hmac_object.hexdigest()
