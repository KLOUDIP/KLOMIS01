# -*- coding: utf-8 -*-
import collections
from odoo import models, tools


class ProjectWorksheetTemplateCustom(models.Model):
    _inherit = 'worksheet.template'

    def _generate_worksheet_model(self):
        self.ensure_one()
        res_model = self.res_model.replace('.', '_')
        name = 'x_%s_worksheet_template_%d' % (res_model, self.id)

        # create access rights and rules
        if not hasattr(self, f'_get_{res_model}_manager_group'):
            raise NotImplementedError(f'Method _get_{res_model}_manager_group not implemented on {res_model}')
        if not hasattr(self, f'_get_{res_model}_user_group'):
            raise NotImplementedError(f'Method _get_{res_model}_user_group not implemented on {res_model}')
        if not hasattr(self, f'_get_{res_model}_access_all_groups'):
            raise NotImplementedError(f'Method _get_{res_model}_access_all_groups not implemented on {res_model}')

        # while creating model it will initialize the init_models method from create of ir.model
        # and there is related field of model_id in mail template so it's going to recursive loop while recompute so used flush
        self.env.flush_all()

        # Generate xml ids for some records: views, actions and models. This will let the ORM handle
        # the module uninstallation (removing all data belonging to the module using their xml ids).
        # NOTE: this is not needed for ir.model.fields, ir.model.access and ir.rule, as they are in
        # delete 'cascade' mode, so their database entries will removed (no need their xml id).
        module_name = getattr(self, f'_get_{res_model}_module_name')()
        xid_values = []
        model_counter = collections.Counter()

        def register_xids(records):
            for record in records:
                model_counter[record._name] += 1
                xid_values.append({
                    'name': "{}_{}_{}".format(
                        name,
                        record._name.replace('.', '_'),
                        model_counter[record._name],
                    ),
                    'module': module_name,
                    'model': record._name,
                    'res_id': record.id,
                    'noupdate': True,
                })
            return records

        # generate the ir.model (and so the SQL table)
        model = register_xids(self.env['ir.model'].sudo().create({
            'name': self.name,
            'model': name,
            'field_id': self._prepare_default_fields_values() + [
                (0, 0, {
                    'name': 'x_name',
                    'field_description': 'Name',
                    'ttype': 'char',
                    'related': 'x_%s_id.name' % res_model,
                }),
            ]
        }))

        self.env['ir.model.access'].sudo().create([{
            'name': name + '_manager_access',
            'model_id': model.id,
            'group_id': getattr(self, '_get_%s_manager_group' % res_model)().id,
            'perm_create': True,
            'perm_write': True,
            'perm_read': True,
            'perm_unlink': True,
        }, {
            'name': name + '_user_access',
            'model_id': model.id,
            'group_id': getattr(self, '_get_%s_user_group' % res_model)().id,
            'perm_create': True,
            'perm_write': True,
            'perm_read': True,
            'perm_unlink': True,
        }])
        self.env['ir.rule'].create([{
            'name': name + '_own',
            'model_id': model.id,
            'domain_force': "[('create_uid', '=', user.id)]",
            'groups': [(6, 0, [getattr(self, '_get_%s_user_group' % res_model)().id])]
        }, {
            'name': name + '_all',
            'model_id': model.id,
            'domain_force': [(1, '=', 1)],
            'groups': [(6, 0, getattr(self, '_get_%s_access_all_groups' % res_model)().ids)],
        }])

        # create the view to extend by 'studio' and add the user custom fields
        __, __, search_view = register_xids(self.env['ir.ui.view'].sudo().create([
            self._prepare_default_form_view_values(model),
            self._prepare_default_tree_view_values(model),
            self._prepare_default_search_view_values(model)
        ]))
        action = register_xids(self.env['ir.actions.act_window'].sudo().create({
            'name': 'Worksheets',
            'res_model': model.model,
            'search_view_id': search_view.id,
            'context': {
                'edit': False,
                'create': False,
                'delete': False,
                'duplicate': False,
            }
        }))

        self.env['ir.model.data'].sudo().create(xid_values)

        # link the worksheet template to its generated model and action
        self.write({
            'action_id': action.id,
            'model_id': model.id,
        })
        # this must be done after form view creation and filling the 'model_id' field
        self.sudo()._generate_qweb_report_template()

        # Add unique constraint on the x_model_id field since we want one worksheet per host record
        conname = '%s_x_%s_id_uniq' % (name, res_model)
        concode = 'unique(x_%s_id)' % (res_model)
        tools.add_constraint(self.env.cr, name, conname, concode)

    def _prepare_default_fields_values(self):
        res = super(ProjectWorksheetTemplateCustom, self)._prepare_default_fields_values()
        custom_fields = [
            (0, 0, {  # needed for proper model creation from demo data
                'name': 'x_worksheet_no',
                'field_description': 'Worksheet No',
                'ttype': 'char',

            }),
            (0, 0, {  # needed for proper model creation from demo data
                'name': 'x_technician_name',
                'field_description': 'Technician Name',
                'ttype': 'many2one',
                'relation': 'res.users',
                'required': True,
                'on_delete': 'cascade',

            }),
            (0, 0, {  # needed for proper model creation from demo data
                'name': 'x_company_id',
                'field_description': 'Company',
                'ttype': 'many2one',
                'relation': 'res.partner',
                'required': True,
                'on_delete': 'cascade',

            }),
            (0, 0, {  # needed for proper model creation from demo data
                'name': 'x_contact_person',
                'field_description': 'Contact Person',
                'ttype': 'many2one',
                'relation': 'res.partner',
                'required': True,
                'on_delete': 'cascade',

            }),
            (0, 0, {  # needed for proper model creation from demo data
                'name': 'x_contact_no',
                'field_description': 'Contact Number',
                'ttype': 'char',
            }),
            (0, 0, {  # needed for proper model creation from demo data
                'name': 'x_job_type',
                'field_description': 'Worksheet Type',
                'ttype': 'many2one',
                'relation': 'project.project',
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
        ]
        return res + custom_fields

    def _prepare_default_form_view_values(self, model):
        """Create a default form view for the model created from the template.
        """
        res_model_name = self.res_model.replace('.', '_')
        form_arch_func = getattr(self, '_default_%s_worksheet_form_arch' % res_model_name, False)
        return {
            'type': 'form',
            'name': 'template_view_' + "_".join(self.name.split(' ')),
            'model': model.model,
            'arch': form_arch_func and form_arch_func() or """
                <form create="false" duplicate="false">
                    <sheet>
                        <h1 invisible="context.get('studio') or context.get('default_x_%s_id')">
                            <field name="x_%s_id"/>
                        </h1>
                        <h1 invisible="context.get('studio') or context.get('default_x_%s_id')">
                            <field name="x_studio_line_id"/>
                        </h1>
                        <group>
                            <field name="x_comments" placeholder="Add details about your intervention..."/>
                            <field name="x_worksheet_no" readonly="1"/>
                            <field name="x_technician_name" />
                            <field name="x_company_id" readonly="1"/>
                            <field name="x_contact_person" readonly="1"/>
                            <field name="x_contact_no" readonly="1"/>
                            <field name="x_job_type" readonly="1"/>
                        </group>
                    </sheet>
                </form>
            """ % (res_model_name, res_model_name, res_model_name)
        }
