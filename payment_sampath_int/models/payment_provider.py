# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only.
from odoo import fields, models


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('sampath_int', "Sampath_int Bank International")],
        ondelete={'sampath_int': 'set default'})
    sampath_int_client_id = fields.Char(
        string="Sampath ClientID", required_if_provider='sampath_int', groups='base.group_system')
    sampath_int_hmac_secret = fields.Char(
        string="Sampath HMAC Secret", groups='base.group_system')
    sampath_int_auth_token = fields.Char(
        string="Auth Token", help="Auth token for confirm the transaction",
        required_if_provider='sampath_int')

    # The HMAC signing, the API call and every payment.transaction override are
    # removed. This provider is inert - disable it before the upgrade.
