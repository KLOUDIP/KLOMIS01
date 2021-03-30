# -*- coding: utf-8 -*-

from lxml import etree

from odoo import models, fields, tools, api, _
from odoo.addons.product_configurator_sale.wizard.product_configurator import ProductConfiguratorSale as BaseProductConfiguratorSale
from odoo.addons.base.models.ir_ui_view import (transfer_field_to_modifiers, transfer_node_to_modifiers, transfer_modifiers_to_node)
from odoo.exceptions import UserError, ValidationError


def generate_mandatory_alternative_selection_list(product_id):
    """Will return list like - ['mandatory'] if only mandatory products assigned to the product template or
    ['alternative'] for only alternative products assigned or ['mandatory', 'alternative'] for if the product have
    both type of sub products"""
    state_extend = []
    if product_id.compulsory_product_ids:
        state_extend.append('mandatory')
    if product_id.non_compulsory_product_ids:
        state_extend.append('alternative')
    return state_extend


def action_config_done(self):
    """Extending Base Method - Parse values and execute final code before closing the wizard"""
    res = super(BaseProductConfiguratorSale, self).action_config_done()
    if res.get("res_model") == self._name:
        return res
    model_name = "sale.order.line"
    line_vals = self._get_order_line_vals(res["res_id"])

    # Call onchange explicit as write and create
    # will not trigger onchange automatically
    order_line_obj = self.env[model_name]
    cfg_session = self.config_session_id
    specs = cfg_session.get_onchange_specifications(model=model_name)
    updates = order_line_obj.onchange(line_vals, ["product_id"], specs)
    values = updates.get("value", {})
    values = cfg_session.get_vals_to_write(values=values, model=model_name)
    values.update(line_vals)

    product_id = self.env['product.product'].browse(values.get('product_id'))

    active_product_types = generate_mandatory_alternative_selection_list(product_id)

    if active_product_types:
        context = {'state_list': active_product_types,
                   'form_name': 'Select Additional Products',
                   'sale_order_id': self.order_id.id,
                   'sale_order_line': self.order_line_id.id if self.order_line_id else False,
                   'main_product_values': values
                   }
        # check if the action come from reconfigure button (sale.order.line)
        if 'mandatory' in active_product_types and 'reconfigure' not in self.env.context:
            context.update({'mandatory_products': product_id.compulsory_product_ids.ids})
        else:
            context.update({'mandatory_products': [], 'state_list': ['alternative']})
        if 'alternative' in active_product_types and 'reconfigure' not in self.env.context:
            context.update({'alternative_products': product_id.non_compulsory_product_ids.ids})
        else:
            sub_products = self.order_id.order_line.mapped('product_id').filtered(lambda x: not x.config_ok).ids
            alternative_products = [x for x in product_id.non_compulsory_product_ids.ids if x not in sub_products]
            if alternative_products:
                context.update({'alternative_products': alternative_products})
        result = {
            'name': _('Select Additional Products'),
            'view_mode': 'form',
            'view_type': 'form',
            'res_model': 'mandatory.alternative.products',
            'type': 'ir.actions.act_window',
            'target': 'new',
            'context': context
        }
        return result
    else:
        if self.order_line_id:
            self.order_line_id.write(values)
        else:
            self.order_id.write({"order_line": [(0, 0, values)]})
        return {'type': 'ir.actions.act_window_close'}


BaseProductConfiguratorSale.action_config_done = action_config_done


class ProductConfigurator(models.TransientModel):
    _inherit = 'product.configurator'

    @api.model
    def add_dynamic_fields(self, res, dynamic_fields, wiz):
        """ Create the configuration view using the dynamically generated
            fields in fields_get()
        """

        field_prefix = self._prefixes.get("field_prefix")
        custom_field_prefix = self._prefixes.get("custom_field_prefix")

        try:
            # Search for view container hook and add dynamic view and fields
            xml_view = etree.fromstring(res["arch"])
            xml_static_form = xml_view.xpath("//group[@name='static_form']")[0]
            xml_dynamic_form = etree.Element(
                "group", colspan="2", name="dynamic_form"
            )
            xml_parent = xml_static_form.getparent()
            xml_parent.insert(
                xml_parent.index(xml_static_form) + 1, xml_dynamic_form
            )
            xml_dynamic_form = xml_view.xpath("//group[@name='dynamic_form']")[
                0
            ]
        except Exception:
            raise UserError(
                _(
                    "There was a problem rendering the view "
                    "(dynamic_form not found)"
                )
            )

        # Get all dynamic fields inserted via fields_get method
        attr_lines = wiz.product_tmpl_id.attribute_line_ids.sorted()

        # Loop over the dynamic fields and add them to the view one by one
        for attr_line in attr_lines:

            attribute_id = attr_line.attribute_id.id
            field_name = field_prefix + str(attribute_id)
            custom_field = custom_field_prefix + str(attribute_id)

            # Check if the attribute line has been added to the db fields
            if field_name not in dynamic_fields:
                continue

            config_steps = wiz.product_tmpl_id.config_step_line_ids.filtered(
                lambda x: attr_line in x.attribute_line_ids
            )

            # attrs property for dynamic fields
            attrs = {"readonly": [], "required": [], "invisible": []}

            if config_steps:
                cfg_step_ids = [str(id) for id in config_steps.ids]
                attrs["invisible"].append(("state", "not in", cfg_step_ids))
                attrs["readonly"].append(("state", "not in", cfg_step_ids))

                # If attribute is required make it so only in the proper step
                if attr_line.required:
                    attrs["required"].append(("state", "in", cfg_step_ids))
            else:
                attrs["invisible"].append(("state", "not in", ["configure"]))
                attrs["readonly"].append(("state", "not in", ["configure"]))

                # If attribute is required make it so only in the proper step
                if attr_line.required:
                    attrs["required"].append(("state", "in", ["configure"]))

            if attr_line.custom:
                pass
                # TODO: Implement restrictions for ranges

            config_lines = wiz.product_tmpl_id.config_line_ids
            dependencies = config_lines.filtered(
                lambda cl: cl.attribute_line_id == attr_line
            )

            # If an attribute field depends on another field from the same
            # configuration step then we must use attrs to enable/disable the
            # required and readonly depending on the value entered in the
            # dependee

            if attr_line.value_ids <= dependencies.mapped("value_ids"):
                attr_depends = {}
                domain_lines = dependencies.mapped("domain_id.domain_line_ids")
                for domain_line in domain_lines:
                    attr_id = domain_line.attribute_id.id
                    attr_field = field_prefix + str(attr_id)
                    attr_lines = wiz.product_tmpl_id.attribute_line_ids
                    # If the fields it depends on are not in the config step
                    # allow to update attrs for all attribute.\ otherwise
                    # required will not work with stepchange using statusbar.
                    # if config_steps and wiz.state not in cfg_step_ids:
                    #     continue
                    if attr_field not in attr_depends:
                        attr_depends[attr_field] = set()
                    if domain_line.condition == "in":
                        attr_depends[attr_field] |= set(
                            domain_line.value_ids.ids
                        )
                    elif domain_line.condition == "not in":
                        val_ids = attr_lines.filtered(
                            lambda l: l.attribute_id.id == attr_id
                        ).value_ids
                        val_ids = val_ids - domain_line.value_ids
                        attr_depends[attr_field] |= set(val_ids.ids)

                for dependee_field, val_ids in attr_depends.items():
                    if not val_ids:
                        continue
                    if not attr_line.custom:
                        attrs["readonly"].append(
                            (dependee_field, "not in", list(val_ids))
                        )

                    if attr_line.required and not attr_line.custom:
                        attrs["required"].append(
                            (dependee_field, "in", list(val_ids))
                        )

            # Create the new field in the view
            node = etree.Element(
                "field",
                name=field_name,
                on_change="1",
                default_focus="1" if attr_line == attr_lines[0] else "0",
                attrs=str(attrs),
                context=str(
                    {
                        "show_attribute": False,
                        "show_price_extra": True,
                        "active_id": wiz.product_tmpl_id.id,
                    }
                ),
                options=str(
                    {
                        "no_create": True,
                        "no_create_edit": True,
                        "no_open": True,
                    }
                ),
            )

            field_type = dynamic_fields[field_name].get("type")
            if field_type == "many2many":
                node.attrib["widget"] = "many2many_tags"
            # Apply the modifiers (attrs) on the newly inserted field in the
            # arch and add it to the view
            self.setup_modifiers(node)
            xml_dynamic_form.append(node)

            if attr_line.custom and custom_field in dynamic_fields:
                widget = ""
                config_session_obj = self.env["product.config.session"]
                custom_option_id = config_session_obj.get_custom_value_id().id

                if field_type == "many2many":
                    field_val = [(6, False, [custom_option_id])]
                else:
                    field_val = custom_option_id

                attrs["readonly"] += [(field_name, "!=", field_val)]
                attrs["invisible"] += [(field_name, "!=", field_val)]
                attrs["required"] += [(field_name, "=", field_val)]

                if config_steps:
                    attrs["required"] += [("state", "in", cfg_step_ids)]

                # TODO: Add a field2widget mapper
                if attr_line.attribute_id.custom_type == "color":
                    widget = "color"
                node = etree.Element(
                    "field", name=custom_field, attrs=str(attrs), widget=widget
                )
                self.setup_modifiers(node)
                xml_dynamic_form.append(node)
        return xml_view

    @api.model
    def setup_modifiers(self, node, field=None, context=None, in_tree_view=False):
        """ Overwriting base method because attrs not worked so we have to write the base method as following
        - In case an attrs error, start looking from this"""
        modifiers = {}
        field = node
        if field is not None:
            transfer_field_to_modifiers(field=node, modifiers=modifiers)
            transfer_node_to_modifiers(
                node=node,
                modifiers=modifiers,
                context=context,
                # in_tree_view=in_tree_view,
            )
            transfer_modifiers_to_node(modifiers=modifiers, node=node)

    def action_next_step(self):
        """Extending Base Method"""
        wizard_action = self.with_context(
            allow_preset_selection=False
        ).get_wizard_action(wizard=self)

        if not self.product_tmpl_id:
            return wizard_action

        if not self.product_tmpl_id.attribute_line_ids:
            raise ValidationError(
                _("Product Template does not have any attribute lines defined")
            )

        next_step = self.config_session_id.get_next_step(
            state=self.state,
            product_tmpl_id=self.product_tmpl_id,
            value_ids=self.value_ids,
            custom_value_ids=self.custom_value_ids,
        )
        # Extend from here - We need to start from the
        # first configuration step, instead of starting from leftover data in the last popup
        if self.state == 'select':
            open_lines = [str(x.id) for x in self.config_session_id.get_open_step_lines()]
            if open_lines:
                next_step = open_lines[0]
        # ----------------------Extend End---------------------------------
        if not next_step:
            return self.action_config_done()
        return self.open_step(step=next_step)
