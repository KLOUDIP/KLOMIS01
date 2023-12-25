# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class LoyaltyGenerateWizard(models.TransientModel):
    _inherit = 'loyalty.generate.wizard'

    def _get_coupon_values(self, partner):
        """
        @override - get values for coupon creation
        """
        self.ensure_one()
        return {
            'program_id': self.program_id.id,
            'points': self.points_granted,
            'expiration_date': self.valid_until,
            'partner_id': False,  # Modified line
            'invoice_partner_id': partner.id if self.mode == 'selected' else False,  # Modified line
        }
