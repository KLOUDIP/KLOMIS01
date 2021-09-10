# -*- coding: utf-8 -*-

import ast
from odoo.addons.coupon.wizard.coupon_generate import CouponGenerate as CouponGenerateBase


def generate_coupon(self):
    """Override core method - Generates the number of coupons entered in wizard field nbr_coupons
    """
    program = self.env['coupon.program'].browse(self.env.context.get('active_id'))

    vals = {'program_id': program.id}

    if self.generation_type == 'nbr_coupon' and self.nbr_coupons > 0:
        for count in range(0, self.nbr_coupons):
            self.env['coupon.coupon'].create(vals)

    if self.generation_type == 'nbr_customer' and self.partners_domain:
        for partner in self.env['res.partner'].search(ast.literal_eval(self.partners_domain)):
            # vals.update({'partner_id': partner.id, 'state': 'sent' if partner.email else 'new'})
            vals.update({'partner_id': False, 'invoice_partner_id': partner.id, 'state': 'sent' if partner.email else 'new'})  # modified line
            coupon = self.env['coupon.coupon'].create(vals)
            subject = '%s, a coupon has been generated for you' % partner.name
            template = self.env.ref('coupon.mail_template_sale_coupon', raise_if_not_found=False)
            if template:
                email_values = {'email_to': partner.email, 'email_from': self.env.user.email or '', 'subject': subject}
                template.send_mail(coupon.id, email_values=email_values, notif_layout='mail.mail_notification_light')


CouponGenerateBase.generate_coupon = generate_coupon
