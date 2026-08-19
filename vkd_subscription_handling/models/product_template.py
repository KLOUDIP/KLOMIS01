from odoo import _, api, fields, models


class ProductTemplate(models.Model):
    _inherit = "product.template"

    is_free_plan = fields.Boolean(
        'Is Free Plan?',
        help='If set, automatically create subscription for new trazet customers')