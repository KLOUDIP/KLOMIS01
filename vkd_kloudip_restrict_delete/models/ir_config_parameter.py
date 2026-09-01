from odoo import api, models

from .ir_model_access import EXTRA_MODELS_PARAM


class IrConfigParameter(models.Model):
    """Re-apply the restriction as soon as the extra-models list changes."""

    _inherit = "ir.config_parameter"

    def _kloudip_reapply_if_needed(self, keys):
        if EXTRA_MODELS_PARAM in keys:
            self.env["ir.model.access"].sudo()._kloudip_apply_delete_restrictions()

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._kloudip_reapply_if_needed(records.mapped("key"))
        return records

    def write(self, vals):
        keys = set(self.mapped("key"))
        res = super().write(vals)
        keys.update(self.mapped("key"))
        self._kloudip_reapply_if_needed(keys)
        return res
