from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

import logging
_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(selection_add=[('sampathbank', 'Sampath Bank')],
                            ondelete={'sampathbank': 'set default'})

    sampathbank_clientId = fields.Integer(string='Client ID')
    sampathbank_hmac_secret = fields.Char(string='Hmac Secret')
    sampathbank_authtoken = fields.Char(string='Authtoken')
    sampathbank_base_url_test = fields.Char('Test Base URL', default='https://sampath.paycorp.lk')
    sampathbank_base_url_production = fields.Char('Production Base URL', default='https://sampath.paycorp.lk')

    def _get_sampathbank_url(self):
        """Get base url based on state of the payment provider"""
        if self.state == 'test':
            url = self.sampathbank_base_url_test
        elif self.state == 'enabled':
            url = self.sampathbank_base_url_production
        else:
            url = ''
        return url