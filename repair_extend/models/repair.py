# -*- coding: utf-8 -*-
from odoo import Command, fields, models, _
from odoo.exceptions import UserError


class RepairOrder(models.Model):
    _inherit = 'repair.order'

    device_sale_id = fields.Many2one('sale.order', string="Device Order", copy=False)
    under_warranty = fields.Boolean(tracking=True)

    def action_create_device_order(self):
        if any(repair.device_sale_id for repair in self):
            concerned_ro = self.filtered('device_sale_id')
            ref_str = "\n".join(ro.name for ro in concerned_ro)
            raise UserError(
                _("You cannot create a quotation for a repair order that is already linked to an existing sale order.\nConcerned repair order(s) :\n") + ref_str)
        if any(not repair.partner_id for repair in self):
            concerned_ro = self.filtered(lambda ro: not ro.partner_id)
            ref_str = "\n".join(ro.name for ro in concerned_ro)
            raise UserError(
                _("You need to define a customer for a repair order in order to create an associated quotation.\nConcerned repair order(s) :\n") + ref_str)
        sale_order_values_list = []
        for repair in self:
            sale_order_values_list.append({
                "company_id": self.company_id.id,
                "partner_id": self.partner_id.id,
                "warehouse_id": self.picking_type_id.warehouse_id.id,
                "device_repair_order_id": repair.id,
            })
        so = self.env['sale.order'].create(sale_order_values_list)
        self.device_sale_id = so.id
        # Add Sale Order Lines for 'add' move_ids
        self._create_device_sale_order_line()
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "views": [[False, "form"]],
            "res_id": so.id,
        }

    def _create_device_sale_order_line(self):
        if not self:
            return
        so_line_vals = []
        for move in self.move_ids:
            so_line_vals.append({
                'order_id': move.repair_id.device_sale_id.id,
                'product_id': move.product_id.id,
                'product_uom_qty': move.product_qty,
            })
            if move.repair_id.under_warranty:
                so_line_vals[-1]['price_unit'] = 0.0
            elif move.price_unit:
                so_line_vals[-1]['price_unit'] = move.price_unit

        self.env['sale.order.line'].create(so_line_vals)

    def action_show_device_order(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "sale.order",
            "views": [[False, "form"]],
            "res_id": self.device_sale_id.id,
        }
