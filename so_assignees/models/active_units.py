# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only.
from odoo import fields, models


class ActiveUnits(models.Model):
    _inherit = 'active.units'

    coordinator_id = fields.Many2one("res.users", string="Assigned To")
    is_coordinator_add = fields.Boolean(string="Coordinator Added")

    # onchange_coordinator_id / update_monthly_rec / update_coordinator_unit_line
    # and the unlink() override are removed: they raise ValidationErrors and
    # write to active.units.monthly, which must not happen while the module is
    # only being kept alive for the upgrade.


class ActiveUnitsMonthly(models.Model):
    _name = "active.units.monthly"
    _description = "Active Units Monthly"

    date = fields.Date(string="Date")
    contract_id = fields.Many2one("fleet.vehicle.log.contract", string="Contract")
    coordinator_id = fields.Many2one("res.users", string="Assigned To")
    unit_id = fields.Many2one("active.units", string="Active Unit")
    value = fields.Integer(string="Value")
