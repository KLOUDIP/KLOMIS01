# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only.
from odoo import fields, models
from odoo.exceptions import UserError


class ResUsers(models.Model):
    _inherit = "res.users"

    uuid_token = fields.Char(string="Token")

    def generate_uuid_token(self):
        # Stub: the BiCom integration is being decommissioned.
        raise UserError(
            "The BiCom Connector is scheduled for removal and no longer issues tokens."
        )
