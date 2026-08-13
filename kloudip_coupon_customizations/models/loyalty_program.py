# -*- coding: utf-8 -*-
from odoo import api, fields, models, _


class LoyaltyProgram(models.Model):
    _inherit = 'loyalty.program'

    allow_redeem_multiple_coupons = fields.Boolean(
        string='Allow Redeem Multiple Coupons',
        help='Enabling this option will allow user to redeem multiple coupons in sale order'
    )

    @api.model
    def _swap_mail_templates(self):
        """
        Overrides core loyalty program communications to use our Odoo 19 compliant custom template.
        This runs automatically when the module updates, bypassing XML noupdate restrictions.
        """
        custom_template = self.env.ref('kloudip_coupon_customizations.mail_template_loyalty_card_custom',
                                       raise_if_not_found=False)
        old_template = self.env.ref('loyalty.mail_template_loyalty_card', raise_if_not_found=False)

        if custom_template and old_template:
            # Update all existing loyalty communication triggers to use the new custom template
            loyalty_mails = self.env['loyalty.mail'].search([('mail_template_id', '=', old_template.id)])
            if loyalty_mails:
                loyalty_mails.write({'mail_template_id': custom_template.id})
