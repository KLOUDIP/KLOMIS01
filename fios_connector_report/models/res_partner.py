# -*- coding: utf-8 -*-
# KLOMIS01 v17 -> v19 REMOVAL SHELL - load-only.
from odoo import models
from odoo.exceptions import UserError


class ResPartner(models.Model):
    _inherit = 'res.partner'

    def action_fios_active_units_send(self):
        # IMPORTANT: this stub is the reason the module is kept at all.
        # A Studio customisation on res.partner binds a button to this method;
        # without it Odoo deactivates that custom view on first load.
        raise UserError(
            "The FIOS active units report is scheduled for removal and is no longer available."
        )
