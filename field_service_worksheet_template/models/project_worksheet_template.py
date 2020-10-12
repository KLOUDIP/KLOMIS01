# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from ast import literal_eval
from lxml import etree
import time

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
from odoo.addons.base.models.ir_model import MODULE_UNINSTALL_FLAG


class ProjectWorksheetTemplateCustom(models.Model):
    _inherit = 'project.worksheet.template'

    def _generate_worksheet_model(self, template):
        name = 'x_project_worksheet_template_' + str(template.id)
        # while creating model it will initialize the init_models method from create of ir.model
        # and there is related field of model_id in mail template so it's going to recusrive loop while recompute so used flush
        self.flush()

        # generate the ir.model (and so the SQL table)
        model = self.env['ir.model'].sudo().create({
            'name': template.name,
            'model': name,
            'field_id': [
                (0, 0, {  # needed for proper model creation from demo data
                    'name': 'x_name',
                    'field_description': 'Name',
                    'ttype': 'char',

                }),
                (0, 0, {  # needed for proper model creation from demo data
                    'name': 'x_worksheet_no',
                    'field_description': 'Worksheet No',
                    'ttype': 'char',

                }),
                (0, 0, {
                    'name': 'x_task_id',
                    'field_description': 'Task',
                    'ttype': 'many2one',
                    'relation': 'project.task',
                    'required': True,
                    'on_delete': 'cascade',
                }),

                (0, 0, {
                    'name': 'x_studio_line_id',
                    'field_description': 'Line Id',
                    'ttype': 'many2one',
                    'relation': 'worksheet.template.line',
                    'required': False,
                    'on_delete': 'cascade',
                }),


                (0, 0, {
                    'name': 'x_comments',
                    'ttype': 'text',
                    'field_description': 'Comments',
                }),
            ]
        })
        # create access rights and rules
        self.env['ir.model.access'].sudo().create({
            'name': name + '_access',
            'model_id': model.id,
            'group_id': self.env.ref('project.group_project_manager').id,
            'perm_create': True,
            'perm_write': True,
            'perm_read': True,
            'perm_unlink': True,
        })
        self.env['ir.model.access'].sudo().create({
            'name': name + '_access',
            'model_id': model.id,
            'group_id': self.env.ref('project.group_project_user').id,
            'perm_create': True,
            'perm_write': True,
            'perm_read': True,
            'perm_unlink': True,
        })
        self.env['ir.rule'].sudo().create({
            'name': name + '_own',
            'model_id': model.id,
            'domain_force': "[('create_uid', '=', user.id)]",
            'groups': [(6, 0, [self.env.ref('project.group_project_user').id])]
        })
        self.env['ir.rule'].sudo().create({
            'name': name + '_all',
            'model_id': model.id,
            'domain_force': [(1, '=', 1)],
            'groups': [(6, 0, [self.env.ref('project.group_project_manager').id])]
        })
        # make the name field related to the task, so we keep consistence with task name
        x_name_field = self.env['ir.model.fields'].search([('model_id', '=', model.id), ('name', '=', 'x_name')])
        x_name_field.sudo().write({'related': 'x_task_id.name'})  # possible only after target field have been created

        x_name_field_seq = self.env['ir.model.fields'].search([('model_id', '=', model.id), ('name', '=', 'x_worksheet_no')])
        x_name_field_seq.sudo().write({'related': 'x_studio_line_id.name'})

        # create the view to extend by 'studio' and add the user custom fields
        form_view = self.env['ir.ui.view'].sudo().create({
            'type': 'form',
            'name': 'template_view_' + "_".join(template.name.split(' ')),
            'model': model.model,
            'arch': """
            <form>
                <sheet>
              
                    <h1 invisible="context.get('studio') or context.get('default_x_task_id')">
                            <field name="x_task_id" domain="[('is_fsm', '=', True)]"/>
                    </h1>
                    <h1 invisible="context.get('studio') or context.get('default_x_studio_line_id')">
                            <field name="x_studio_line_id" domain="[('is_fsm', '=', True)]"/>
                    </h1>
                    <group class="o_fsm_worksheet_form">
                        <group>
                            <field name="x_comments"/>
                            <field name="x_worksheet_no" readonly="1"/>
                        </group>
                        <group>
                        </group>
                    </group>
                </sheet>
            </form>
            """
        })
        action = self.env['ir.actions.act_window'].sudo().create({
            'name': 'Worksheets',
            'res_model': model.model,
            'view_mode': 'tree,form',
            'target': 'current',
            'context': {
                'edit': False,
                'create': False,
                'delete': False,
                'duplicate': False,
            }
        })

        # generate xml ids for some records: views, actions and models. This will let the ORM handle the module uninstallation (removing all data belonging
        # to the module using their xml ids).
        # NOTE: this is not needed for ir.model.fields, ir.model.access and ir.rule, as they are in delete 'cascade' mode, so their databse entries will removed
        # (no need their xml id).
        action_xmlid_values = {
            'name': 'template_action_' + "_".join(template.name.split(' ')),
            'model': 'ir.actions.act_window',
            'module': 'industry_fsm_report',
            'res_id': action.id,
            'noupdate': True,
        }
        model_xmlid_values = {
            'name': 'model_x_custom_worksheet_' + "_".join(model.model.split('.')),
            'model': 'ir.model',
            'module': 'industry_fsm_report',
            'res_id': model.id,
            'noupdate': True,
        }
        view_xmlid_values = {
            'name': 'form_view_custom_' + "_".join(model.model.split('.')),
            'model': 'ir.ui.view',
            'module': 'industry_fsm_report',
            'res_id': form_view.id,
            'noupdate': True,
        }
        self.env['ir.model.data'].sudo().create([action_xmlid_values, model_xmlid_values, view_xmlid_values])

        # link the worksheet template to its generated model and action
        template.write({
            'action_id': action.id,
            'model_id': model.id,
        })
        # this must be done after form view creation and filling the 'model_id' field
        template.sudo()._generate_qweb_report_template()
        return template