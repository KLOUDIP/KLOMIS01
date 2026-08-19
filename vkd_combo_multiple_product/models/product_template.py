# -*- coding: utf-8 -*-
from odoo import api, fields, models, _
from odoo.exceptions import UserError

class ProductTemplate(models.Model):
    _inherit = 'product.template'

    @api.constrains('combo_ids')
    def _check_combo_unicity(self):
        if not self.ids:
            return

        templates_to_check = self.filtered(lambda t: t.combo_ids)
        if not templates_to_check:
            return

        domain = [
            ('combo_ids', 'in', templates_to_check.combo_ids.ids),
            ('id', 'not in', templates_to_check.ids)
        ]
        other_templates_using_same_combos = self.env['product.template'].search(domain, limit=1)

        if other_templates_using_same_combos:
            for template in templates_to_check:
                search_domain = [
                    ('combo_ids', 'in', template.combo_ids.ids),
                    ('id', '!=', template.id)
                ]
                conflicting_templates = self.env['product.template'].search(search_domain)

                if conflicting_templates:
                    all_conflicting_combos = conflicting_templates.mapped('combo_ids')
                    problematic_combos = template.combo_ids & all_conflicting_combos

                    if problematic_combos:
                        raise UserError(_(
                            "Validation Error on Product '%s':\n"
                            "The following Combo Choice(s) are already used in other product(s) and cannot be reused: %s"
                        ) % (template.name, ', '.join(problematic_combos.mapped('name'))))