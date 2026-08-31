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
        """ Post to the Paycorp proxy and ALWAYS return a parsed dict.

        Paycorp can answer 200 OK with a body that is not JSON (empty body,
        an HTML error page, a WAF/proxy block page). Calling `.json()` on that
        raises `json.JSONDecodeError: Expecting value: line 1 column 1 (char 0)`,
        which Odoo shows to the shopper as "Payment processing failed".
        Everything below exists so that the raw body reaches the log and the
        shopper gets a meaningful message instead.
        """
        self.ensure_one()
        url = self._sampath_get_api_url()

        # The HMAC must be computed over the EXACT bytes that are sent, so build
        # the body once and post it with `data=`, never with `json=`.
        raw_payload = json.dumps(payload, separators=(',', ':'))
        hmac_secret = self._sampath_generate_hmac(raw_payload)

        headers = {
            'AUTHTOKEN': self.sampath_auth_token,
            'HMAC': hmac_secret,
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

        _logger.info(
            "Sampath: sending %s to %s\npayload: %s",
            (payload or {}).get('operation'), url, pprint.pformat(payload),
        )

        try:
            response = requests.post(
                url, data=raw_payload.encode('utf-8'), headers=headers, timeout=30,
            )
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            _logger.exception("Sampath: unable to reach endpoint at %s", url)
            raise ValidationError(
                "Sampath: " + _("Could not establish the connection to the API.")
            )

        body = response.text or ''

        # Log the raw answer unconditionally: this is the only place the real
        # cause of a non-JSON reply is visible.
        _logger.info(
            "Sampath: HTTP %s from %s (content-type: %s)\nbody: %s",
            response.status_code,
            url,
            response.headers.get('Content-Type'),
            body[:2000] if body else '<EMPTY BODY>',
        )

        try:
            data = response.json()
        except ValueError:
            _logger.error(
                "Sampath: non-JSON response (HTTP %s, content-type %s). "
                "Body was:\n%s",
                response.status_code,
                response.headers.get('Content-Type'),
                body[:2000] if body else '<EMPTY BODY>',
            )
            raise ValidationError("Sampath: " + _(
                "The gateway returned an unreadable response (HTTP %(status)s). "
                "Raw answer: %(body)s",
                status=response.status_code,
                body=(body[:300] if body.strip() else _("empty body")),
            ))

        if response.status_code != 200:
            error_message = data.get('message') or data.get('errorMessage') or body[:300]
            error_code = data.get('error') or data.get('errorCode') or response.status_code
            _logger.error(
                "Sampath: API error at %s with data:\n%s\nresponse:\n%s",
                url, pprint.pformat(payload), pprint.pformat(data),
            )
            raise ValidationError("Sampath: " + _(
                "The communication with the API failed. Information: '%s' (code %s)",
                error_message, error_code,
            ))

        return data

    def _sampath_generate_hmac(self, raw_payload):
        """ Generate the HMAC header for the exact request body being sent.

        :param str raw_payload: the serialised JSON body, byte-for-byte as posted
        """
        if not self.sampath_hmac_secret:
            raise ValidationError(
                _("Sampath HMAC Secret is not configured. Please check your payment provider settings."))

        # Accept a dict for backwards compatibility with the previous signature.
        if isinstance(raw_payload, dict):
            raw_payload = json.dumps(raw_payload, separators=(',', ':'))

        hmac_object = hmac.new(
            key=self.sampath_hmac_secret.encode('utf-8'),
            msg=raw_payload.encode('utf-8'),
            digestmod=hashlib.sha256
        )

        return hmac_object.hexdigest()
