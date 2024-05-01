# -*- coding: utf-8 -*-
from odoo import models, fields

class ResPartner(models.Model):
    _inherit = 'res.partner'

    coordinator_assigned_ids = fields.One2many("coordinator.unit.line", "partner_id", string="Unit Count")
