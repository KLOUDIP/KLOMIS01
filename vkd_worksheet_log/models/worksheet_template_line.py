import pytz
import datetime
from ast import literal_eval
from odoo import models, fields, api, _
from odoo.exceptions import UserError


class WorksheetTemplateLine(models.Model):
    _inherit = 'worksheet.template.line'

    def _get_sri_lanka_time(self):
        sri_lanka_tz = pytz.timezone('Asia/Colombo')
        utc_now = datetime.datetime.utcnow()
        local_time = pytz.utc.localize(utc_now).astimezone(sri_lanka_tz)
        return local_time.strftime("%Y-%m-%d %H:%M:%S")

    @api.model
    def create(self, vals):
        if 'name' in vals:
            if vals['name'] == False:
                vals['name'] = self.env['ir.sequence'].next_by_code('worksheet.template.line', sequence_date=None) or _(
                    'New')

        result = super(WorksheetTemplateLine, self).create(vals)

        if result.project_task_id:
            current_user = self.env.user.name
            current_time = self._get_sri_lanka_time()
            worksheet_number = result.name or 'Unknown'

            log_message = _("Added worksheet number: %s At Date/time: %s By user: %s") % (
                worksheet_number, current_time, current_user
            )
            result.project_task_id.message_post(body=log_message, message_type='comment')

        return result

    def write(self, vals):
        skip_fields = {'line_add', 'worksheet_id', '__last_update', 'access_token',
                       'access_url', 'fsm_is_sent', 'project_id', 'customer_signature'}

        has_meaningful_changes = False
        for key in vals:
            if key not in skip_fields:
                has_meaningful_changes = True
                break

        if has_meaningful_changes:
            changes_to_log = {}
            for record in self:
                if record.project_task_id:
                    record_changes = {}
                    for field, new_value in vals.items():
                        if field not in skip_fields:
                            old_value = getattr(record, field, None)
                            if hasattr(old_value, 'id'):
                                old_value = old_value.id
                            if old_value != new_value:
                                record_changes[field] = (old_value, new_value)
                    if record_changes:
                        changes_to_log[record.id] = record_changes

        result = super(WorksheetTemplateLine, self).write(vals)

        if has_meaningful_changes:
            for record in self:
                if record.id in changes_to_log and changes_to_log[record.id]:
                    current_user = self.env.user.name
                    current_time = self._get_sri_lanka_time()
                    worksheet_number = record.name or 'Unknown'

                    changed_fields = []
                    for field, (old_val, new_val) in changes_to_log[record.id].items():
                        field_obj = record._fields.get(field)
                        field_display = field_obj.string if field_obj else field

                        if field_obj and field_obj.type == 'many2one' and new_val:
                            model = field_obj.comodel_name
                            try:
                                if old_val:
                                    old_record = self.env[model].browse(old_val)
                                    old_val = old_record.display_name
                                if new_val:
                                    new_record = self.env[model].browse(new_val)
                                    new_val = new_record.display_name
                            except:
                                pass  # Just use the IDs if lookup fails

                        changed_fields.append(f"{field_display}: {old_val} → {new_val}")

                    changes_text = ", ".join(changed_fields)
                    log_message = _("Edited worksheet number: %s (Changes: %s) At Date/time: %s By user: %s") % (
                        worksheet_number, changes_text, current_time, current_user
                    )

                    record.project_task_id.message_post(body=log_message, message_type='comment')

        return result

    def unlink(self):
        log_data = []
        for record in self:
            if record.project_task_id:
                current_user = self.env.user.name
                current_time = self._get_sri_lanka_time()
                worksheet_number = record.name or 'Unknown'

                log_data.append({
                    'task': record.project_task_id,
                    'message': _("Deleted worksheet number: %s At Date/time: %s By user: %s") % (
                        worksheet_number, current_time, current_user
                    )
                })

        result = super(WorksheetTemplateLine, self).unlink()

        for log in log_data:
            log['task'].message_post(body=log['message'], message_type='comment')

        return result

    def action_form_worksheet_template(self):
        if self.project_task_id:
            current_user = self.env.user.name
            current_time = self._get_sri_lanka_time()
            worksheet_number = self.name or 'Unknown'

            log_message = _("Opened worksheet number: %s At Date/time: %s By user: %s") % (
                worksheet_number, current_time, current_user
            )

            self.project_task_id.message_post(body=log_message, message_type='comment')

        template_id = self.template_id
        get_line_id = self.id
        worksheet_id = self.worksheet_id
        action = template_id.action_id.read()[0]
        if get_line_id:
            worksheet = self.env[template_id.model_id.model].sudo().search([('x_studio_line_id', '=', get_line_id)],
                                                                           limit=1)

            if worksheet:
                action = template_id.action_id.read()[0]
                context = literal_eval(action.get('context', '{}'))
                action.update({
                    'res_id': worksheet.sudo().id,
                    'views': [(False, 'form')],
                })

                return action
            else:
                raise UserError(_("This Template has no worksheet "))

    def action_fsm_worksheet_template(self):
        if self.project_task_id:
            current_user = self.env.user.name
            current_time = self._get_sri_lanka_time()
            worksheet_number = self.name or 'Unknown'

            log_message = _("Clicked UPDATE button for worksheet number: %s At Date/time: %s By user: %s") % (
                worksheet_number, current_time, current_user
            )

            self.project_task_id.message_post(body=log_message, message_type='comment')

        return super(WorksheetTemplateLine, self).action_fsm_worksheet_template()
