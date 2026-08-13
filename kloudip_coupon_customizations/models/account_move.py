# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, Command
from odoo.exceptions import ValidationError


class AccountMove(models.Model):
    _inherit = 'account.move'

    refund_move = fields.Boolean(string='Refund Move')
    coupon_ids = fields.Many2many('loyalty.card', string='Coupons', copy=False)
    visible_coupon_group = fields.Boolean(
        string='Visible Coupon Group',
        help='For UI Purpose',
        compute='_compute_visible_coupon_group'
    )
    coupons_email_sent = fields.Boolean(string='Coupon Email Sent', copy=False)

    def action_switch_move_type(self):
        """ Safe override instead of Monkey Patch """
        # Only intercept the logic if we are explicitly passing the coupon context
        if self.env.context.get('credit_note_with_coupon'):
            if any(move.posted_before for move in self):
                raise ValidationError(_("You cannot switch the type of a posted document."))
            if any(move.move_type == "entry" for move in self):
                raise ValidationError(_("This action isn't available for this document."))

            for move in self:
                if move.amount_total == 0:
                    in_out, old_move_type = move.move_type.split('_')
                    new_move_type = f"{in_out}_{'invoice' if old_move_type == 'refund' else 'refund'}"
                    move.name = False
                    move.write({
                        'move_type': new_move_type,
                        'partner_bank_id': False,
                        'currency_id': move.currency_id.id,
                    })
                    move.write({
                        'line_ids': [
                            Command.update(line.id, {'quantity': -line.quantity})
                            for line in move.line_ids
                            if line.display_type == 'product'
                        ]
                    })
            return True

        # For all other standard invoices, let Odoo 19's core engine handle it
        return super(AccountMove, self).action_switch_move_type()

    @api.depends('coupon_ids')
    def _compute_visible_coupon_group(self):
        """Compute either coupon group is visible or not"""
        for record in self:
            record.visible_coupon_group = bool(record.coupon_ids)

    def send_coupon_email(self):
        """Send email for the customer notifying generated coupons"""
        self.ensure_one()
        for coupon in self.coupon_ids:
            subject = '%s, a coupon has been generated for you' % (self.partner_id.name,)

            # Use the new custom template first
            template = self.env.ref('kloudip_coupon_customizations.mail_template_loyalty_card_custom',
                                    raise_if_not_found=False)

            # Fallback for safety
            if not template:
                template = self.env.ref('loyalty.mail_template_loyalty_card', raise_if_not_found=False)

            if template:
                email_values = {
                    'email_to': self.partner_id.email,
                    'email_from': self.env.user.email or '',
                    'subject': subject
                }
                template.send_mail(coupon.id, email_values=email_values, notif_layout='mail.mail_notification_light')
        # post message to logger
        self.message_post(
            body=_("Emails sent for the customer - %s, regarding generated coupons.") % self.partner_id.name)
        self.update({'coupons_email_sent': True})
        return True

    def action_post(self):
        """Override core method for create coupons and sending emails about the created coupons.

        NOTE: action_post() is called on multi-record sets (e.g. the bank statement
        line cron posts a whole batch at once), so every access to move-level fields
        must be done per record, never on ``self``.
        """
        res = super(AccountMove, self).action_post()

        for move in self:
            # only customer invoices need to create coupons
            if move.move_type != 'out_invoice':
                continue

            account_move_line_ids = move.invoice_line_ids.filtered(
                lambda x: (x.display_type not in ('line_section', 'line_note') and x.price_unit > 0)
                          and x.product_id and x.product_id.is_coupon_product
            )
            if not account_move_line_ids:
                continue

            all_coupons = []
            for line in account_move_line_ids:
                # loop through move line quantities
                coupons = self.env['loyalty.card']
                for _i in range(int(line.quantity)):
                    # generate coupon
                    coupon = self.env['loyalty.card'].create({
                        'program_id': line.product_id.coupon_program_id.id,
                        'partner_id': False,
                        'invoice_partner_id': move.partner_id.id,
                        'coupon_product_id': line.product_id.id,
                        'points': 1,
                        'order_id': line.sale_line_ids.mapped('order_id')[0].id if line.sale_line_ids else False,
                        'invoice_id': move.id
                    })
                    coupons |= coupon

                if coupons:
                    # writing values to coupon_ids field
                    move.coupon_ids = [Command.link(c.id) for c in coupons]
                    # sort data for the post message
                    all_coupons.append({'product': line.product_id, 'coupons': coupons})

            # post message to chatter with linked coupon
            if all_coupons:
                move.message_post_with_source(
                    'kloudip_coupon_customizations.coupon_created_message',
                    render_values={
                        'data': all_coupons,
                        'partner_generate_email_for_coupons': False
                    },
                    subtype_xmlid='mail.mt_note'
                )
        return res

    def unlink(self):
        """Override core method for cancel relevant coupon when invoice unlink"""
        for rec in self:
            coupons = self.env['loyalty.card'].search([('invoice_id', '=', rec.id)])
            coupons.write({'state': 'cancel'})
            for coupon in coupons:
                coupon.message_post(body='Invoice (%s) deleted. Stage changed to Cancelled.' % self.display_name)
        return super(AccountMove, self).unlink()

    def button_draft(self):
        """Override core method for cancel relevant coupon when invoice set state to draft"""
        for rec in self:
            coupons = self.env['loyalty.card'].search([('invoice_id', '=', rec.id)])
            coupons.write({'state': 'cancel'})
            for coupon in coupons:
                coupon.message_post(body='Invoice (%s) set to draft. Stage changed to Cancelled.' % self.display_name)
        return super(AccountMove, self).button_draft()