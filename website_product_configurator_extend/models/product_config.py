from odoo import api, fields, models, _

class ProductConfigLine(models.Model):
    _inherit = "product.config.line"

    product_ids = fields.Many2many(comodel_name="product.product", id1="pro_conf_id", id2="pro_var_id", string="Variant")