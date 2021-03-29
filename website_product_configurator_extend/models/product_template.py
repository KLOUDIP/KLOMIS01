from odoo import api, fields, models, _

class ProductTemplate(models.Model):
    _inherit = "product.template"

    @api.model
    def _complete_inverse_exclusions(self, exclusions):
        rec = super(ProductTemplate, self)._complete_inverse_exclusions(exclusions)
        order = self.env.user.last_website_so_id
        product_ids = order.order_line.filtered(lambda x: x.config_ok == True).mapped('product_id').non_compulsory_product_ids.product_template_attribute_value_ids.ids
        all = order.order_line.filtered(lambda x: x.config_ok == True).mapped('product_id').non_compulsory_product_ids.product_tmpl_id.valid_product_template_attribute_line_ids.product_template_value_ids.ids
        exclusions = list(set(all).difference(set(product_ids)))
        key_list = list(rec.keys())

        common_variant = list(set(key_list).intersection(exclusions))

        if common_variant:
            for key in rec:
               rec[key] = rec[key] + common_variant
        return rec
