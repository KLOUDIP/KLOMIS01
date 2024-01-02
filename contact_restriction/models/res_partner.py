# -*- coding: utf-8 -*-

from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_blocked = fields.Boolean(string="Is Blocked", default=False, tracking=True)

    def action_block_contact(self):
        self.write({'is_blocked': True})
        if not self.parent_id:
            self.child_ids.write({'is_blocked': True})

    def action_unblock_contact(self):
        self.write({'is_blocked': False})
        if not self.parent_id:
            self.child_ids.write({'is_blocked': False})
