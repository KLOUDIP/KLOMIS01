# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.addons.account.models.account_move import AccountMove as AccountMoveBase


def action_switch_invoice_into_refund_credit_note(self):
    """Overload core method to change line values when move amount total == 0"""
    if any(move.move_type not in ('in_invoice', 'out_invoice') for move in self):
        raise ValidationError(_("This action isn't available for this document."))

    for move in self:
        reversed_move = move._reverse_move_vals({}, False)
        new_invoice_line_ids = []
        for cmd, virtualid, line_vals in reversed_move['line_ids']:
            if not line_vals['exclude_from_invoice_tab']:
                new_invoice_line_ids.append((0, 0, line_vals))
        if move.amount_total < 0 or (self.env.context.get('credit_note_with_coupon', False) and move.amount_total == 0):
            # Inverse all invoice_line_ids
            for cmd, virtualid, line_vals in new_invoice_line_ids:
                line_vals.update({
                    'quantity': -line_vals['quantity'],
                    'amount_currency': -line_vals['amount_currency'],
                    'debit': line_vals['credit'],
                    'credit': line_vals['debit']
                })
        move.write({
            'move_type': move.move_type.replace('invoice', 'refund'),
            'invoice_line_ids': [(5, 0, 0)],
            'partner_bank_id': False,
        })
        move.write({'invoice_line_ids': new_invoice_line_ids})


AccountMoveBase.action_switch_invoice_into_refund_credit_note = action_switch_invoice_into_refund_credit_note


class AccountMove(models.Model):
    _inherit = 'account.move'

    refund_move = fields.Boolean(string='Refund Move')
    coupon_ids = fields.Many2many('coupon.coupon', string='Coupons', copy=False)
    visible_coupon_group = fields.Boolean('Visible Coupon Group', help='For UI Purpose',
                                          compute='_compute_visible_coupon_group')
    coupons_email_sent = fields.Boolean(string='Coupon Email Sent', copy=False)

    def _compute_visible_coupon_group(self):
        """Compute either coupon group is visible or not"""
        visible_coupon_group = False
        if self.coupon_ids:
            visible_coupon_group = True
        self.update({'visible_coupon_group': visible_coupon_group})

    def send_coupon_email(self):
        """Send email for the customer notifying generated coupons"""
        for coupon in self.coupon_ids:
            subject = '%s, a coupon has been generated for you' % (self.partner_id.name,)
            template = self.env.ref('coupon.mail_template_sale_coupon', raise_if_not_found=False)
            if template:
                email_values = {'email_to': self.partner_id.email, 'email_from': self.env.user.email or '',
                                'subject': subject}
                template.send_mail(coupon.id, email_values=email_values,
                                   notif_layout='mail.mail_notification_light')
        # post message to logger
        self.message_post(body=_("Emails sent for the customer - %s, regarding generated coupons.") % self.partner_id.name)
        self.update({'coupons_email_sent': True})
        return True

    def action_post(self):
        """Override core method for create coupons and sending emails about the created coupons"""
        res = super(AccountMove, self).action_post()
        account_move_line_ids = self.invoice_line_ids.filtered(lambda x: (x.display_type not in ('line_section', 'line_note') and x.price_unit > 0) and x.product_id and x.product_id.is_coupon_product)
        # check account move type(only invoice type invoices need to create coupons)
        account_move_line_ids = account_move_line_ids if self.move_type == 'out_invoice' else self.env['account.move.line']
        all_coupons = []
        for line in account_move_line_ids:
            # loop through move line quantities
            coupons = []
            for i in range(int(line.quantity)):
                # generate coupon
                coupon = self.env['coupon.coupon'].create({
                    'program_id': line.product_id.coupon_program_id.id,
                    'partner_id': False,
                    'invoice_partner_id': self.partner_id.id,
                    'coupon_product_id': line.product_id.id,
                    'state': 'sent' if self.partner_id.email else 'new',
                    'invoice_id': self.id
                })
                coupons.append(coupon)
                # writing values to coupon_ids field
                self.update({'coupon_ids': [(4, coupon.id)]})
                # feature removed
                # send specific email to customer FIXME: Performance when sending multiple emails for each quantity
                # if self.partner_id.generate_email_for_coupons:  # checking generate email for coupons setting enabled for invoice partner
                #     subject = '%s, a coupon has been generated for you' % (self.partner_id.name,)
                #     template = self.env.ref('coupon.mail_template_sale_coupon', raise_if_not_found=False)
                #     if template:
                #         email_values = {'email_to': self.partner_id.email, 'email_from': self.env.user.email or '',
                #                         'subject': subject}
                #         template.send_mail(coupon.id, email_values=email_values,
                #                            notif_layout='mail.mail_notification_light')
            # sort data for the post message
            all_coupons.append({'product': line.product_id, 'coupons': coupons})
        # post message to chatter with linked coupon
        if all_coupons:
            self.message_post_with_view('kloudip_coupon_customizations.coupon_created_message',
                                        values={'data': all_coupons, 'partner_generate_email_for_coupons': False},
                                        subtype_id=self.env.ref('mail.mt_note').id)
            # see data> mail_data.xml file (partner_generate_email_for_coupons)
            # self.message_post_with_view('kloudip_coupon_customizations.coupon_created_message',
            #                             values={'data': all_coupons, 'partner_generate_email_for_coupons': self.partner_id.generate_email_for_coupons},
            #                             subtype_id=self.env.ref('mail.mt_note').id)
        return res

    def unlink(self):
        """Override core method for cancel relevant coupon when invoice unlink"""
        for rec in self:
            coupons = self.env['coupon.coupon'].search([('invoice_id', '=', rec.id)])
            coupons.update({'state': 'cancel'})
            for coupon in coupons:
                coupon.message_post(body='Invoice (%s) deleted. Stage changed to Cancelled.' % self.display_name)
        return super(AccountMove, self).unlink()

    def button_draft(self):
        """Override core method for cancel relevant coupon when invoice set state to draft"""
        for rec in self:
            coupons = self.env['coupon.coupon'].search([('invoice_id', '=', rec.id)])
            coupons.update({'state': 'cancel'})
            for coupon in coupons:
                coupon.message_post(body='Invoice (%s) set to draft. Stage changed to Cancelled.' % self.display_name)
        return super(AccountMove, self).button_draft()
