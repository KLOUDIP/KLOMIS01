# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only.
from odoo import models
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def action_view_call_history(self):
        # Stub kept so any view or Studio customisation calling this button
        # remains valid through the upgrade.
        raise UserError("The BiCom Connector is scheduled for removal.")
