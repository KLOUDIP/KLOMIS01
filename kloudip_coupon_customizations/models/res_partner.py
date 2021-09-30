# -*- encoding: utf-8 -*-

from odoo import models, fields, api, _


class ResPartner(models.Model):
    _inherit = 'res.partner'

    # remove feature
    # generate_email_for_coupons = fields.Boolean(string='Generate E-mails for Coupons')
