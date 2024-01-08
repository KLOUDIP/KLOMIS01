# -*- coding: utf-8 -*-

from odoo import fields, models


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('sampath', "Sampath")], ondelete={'sampath': 'set default'})
    sampath_client_id = fields.Char(
        string="Sampath ClientID", required_if_provider='sampath', groups='base.group_system')
    sampath_auth_token = fields.Char(
        string="Auth Token", help="Auth token for confirm the transaction", required_if_provider='sampath')
