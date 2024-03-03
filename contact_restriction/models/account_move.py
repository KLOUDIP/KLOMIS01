# -*- coding: utf-8 -*-

from odoo import models, api
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'partner_id' in vals and 'partner_id' in vals:
                partner = self.env['res.partner'].browse(vals.get('partner_id'))
                if partner and partner.is_blocked:
                    raise UserError("This contact is blocked. You cannot create a Sales Order.")
        return super(AccountMove, self).create(vals_list)

    def write(self, values):
        rec = super(AccountMove, self).write(values)
        if self.partner_id.is_blocked:
            raise UserError("This contact is blocked.")
        return rec
