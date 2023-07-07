# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class CouponCoupon(models.Model):
    _name = 'coupon.coupon'
    _inherit = ['coupon.coupon', 'mail.thread', 'mail.activity.mixin']

    invoice_id = fields.Many2one('account.move', string='Invoice')
    credit_note_id = fields.Many2one('account.move', string='Credit Note', help='When refunded credit note will create for 1 quantity.')
    coupon_product_id = fields.Many2one('product.product', string='Coupon Product')
    state = fields.Selection(selection_add=[('refunded', 'Refunded')], ondelete={'refunded': 'cascade'})
    # when adding coupons from sale order, we need to load coupons that are created for parent company also. so we
    # added new field to not disturb core functionality
    invoice_partner_id = fields.Many2one('res.partner', string='Partner',
                                         help='If the coupon created from invoice, this field will store invoice customer.')

    def _check_coupon_code(self, order, partner_id):
        """Override core method to raise error for refunded coupons and remove error if the program can redeem
        multiple coupons"""
        order_date = order.date_order.date()
        message = super(CouponCoupon, self)._check_coupon_code(order_date, partner_id)
        # handle multiple coupons
        if message.get('error', False) == _('A Coupon is already applied for the same reward') and self.program_id.allow_redeem_multiple_coupons:
            order_lines = order.order_line.filtered(lambda x: (x.display_type not in ('line_section', 'line_note')))
            product_qty = sum(order_lines.filtered(lambda x: x.price_unit > 0).mapped('product_uom_qty'))
            discount_qty = sum(order_lines.filtered(lambda x: x.price_unit < 0).mapped('product_uom_qty'))
            if product_qty == discount_qty:
                message = {'error': _('You can only add %s coupon%s for this sale order') % (int(product_qty), ('s' if product_qty > 1 else ''))}
            else:
                message = {}
        # handle refunded coupons
        if self.state == 'refunded':
            message = {'error': _('This coupon is refunded (%s).') % (self.code)}
        elif len(order.order_line.filtered(lambda x: x.product_id.id in self.program_id.discount_specific_product_ids.ids)) > 1:
            message = {'error': _('You can only add 1 order line with products in discount specific products (Coupon Program - %s)') % (self.program_id.name)}
        # elif len(order.order_line.mapped('coupon_program_id')) > 0:
        #     message = {'error': _('You can only add 1 coupon program to a sale order!')}
        elif order.order_line.mapped('coupon_program_id').id and order.order_line.mapped('coupon_program_id').id != self.program_id.id:
            message = {'error': _('You can only add 1 coupon program to a sale order!')}
        return message

    def action_refund_coupon(self):
        journals = self.env['account.move'].browse(self.invoice_id.ids).journal_id.filtered(lambda x: x.active)
        # raise ValidationError(journals[0])
        """create credit note for assigned invoice id"""
        move_action = self.env['account.move.reversal'].with_context(active_id=self.invoice_id.id, active_ids=self.invoice_id.ids).create({
            'refund_method': 'refund',
            'move_ids': self.env['account.move'].browse(self.invoice_id.ids),
            'journal_id': journals[0].id if journals else None
        }).reverse_moves()
        # find credit note from action
        credit_note = self.env[move_action['res_model']].browse(move_action['res_id'])
        move_lines = []
        invoice_line_ids = credit_note.invoice_line_ids.filtered(lambda x: not x.display_type and x.product_id.is_coupon_product)
        if len(invoice_line_ids) != 1:
            # TODO: Implement if needed
            raise ValidationError('Multiple coupon products found.')
        for line in invoice_line_ids:
            # remove unbalanced entry error pop up (check_move_validity=False)
            # line.with_context(check_move_validity=False).update({'quantity': 1.00})
            line_data = line.copy_data()[0]
            line_data.update({'quantity': 1.00})
            move_lines.append((0, 0, line_data))
        credit_note.line_ids.unlink()
        credit_note.update({'invoice_line_ids': move_lines})

        # update necessary fields
        self.update({'state': 'refunded', 'credit_note_id': credit_note.id})
        return True

    def name_get(self):
        """"Override name get for show coupon program name"""
        result = []
        for coupon in self:
            name = coupon.code + ' - ' + coupon.program_id.name
            result.append((coupon.id, name))
        return result
