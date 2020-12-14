# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict

from odoo import fields, models
from odoo.tools import float_is_zero


class AccountMove(models.Model):
    _inherit = 'account.move'

    project_id = fields.Many2one("project.project", string="Task Type")