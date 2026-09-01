from odoo import api, models


class WorksheetTemplate(models.Model):
    """Keep the delete restriction in place for templates created later.

    Creating a worksheet template generates a brand-new model together with a
    fresh set of ``ir.model.access`` lines that grant unlink to the worksheet
    users. Re-apply the restriction straight away, otherwise a template added
    after the module was installed would come with a working Delete action.
    """

    _inherit = "worksheet.template"

    @api.model_create_multi
    def create(self, vals_list):
        templates = super().create(vals_list)
        self.env["ir.model.access"].sudo()._kloudip_apply_delete_restrictions()
        return templates
