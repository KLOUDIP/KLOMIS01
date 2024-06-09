# -*- coding: utf-8 -*-
from odoo import _, models


class MailComposer(models.TransientModel):
    _inherit = 'mail.compose.message'

    def _action_send_mail_comment(self, res_ids):
        message = super(MailComposer, self)._action_send_mail_comment(res_ids)
        if self.model == 'worksheet.template.line':
            post_values_all = self._prepare_mail_values(res_ids)
            for res_id, post_values in post_values_all.items():
                worksheet_line = self.env['worksheet.template.line'].browse(res_id)
                if worksheet_line:
                        worksheet_line.project_task_id.message_post(**post_values)
        return message
