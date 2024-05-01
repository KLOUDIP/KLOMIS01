# -*- coding: utf-8 -*-
import babel.dates
from odoo import models, fields

MONTH_SELECTION = [
    ('1', 'January'),
    ('2', 'February'),
    ('3', 'March'),
    ('4', 'April'),
    ('5', 'May'),
    ('6', 'June'),
    ('7', 'July'),
    ('8', 'August'),
    ('9', 'September'),
    ('10', 'October'),
    ('11', 'November'),
    ('12', 'December'),
]

class CoordinatorUnitLine(models.Model):
    _name = 'coordinator.unit.line'

    year = fields.Char(string="Year")
    month = fields.Selection(selection=MONTH_SELECTION, string="Month")
    count = fields.Integer(string="Unit Count")
    partner_id = fields.Many2one("res.partner", string="Contact")
