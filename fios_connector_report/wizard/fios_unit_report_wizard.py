from odoo import fields, models


class FIOSUnitReportWizard(models.TransientModel):
    _name = 'fios.unit.report.wizard'

    billing_month = fields.Selection([('January', 'January'),
                                      ('February', 'February'),
                                      ('March', 'March'),
                                      ('April', 'April'),
                                      ('May', 'May'),
                                      ('June', 'June'),
                                      ('July', 'July'),
                                      ('August', 'August'),
                                      ('September', 'September'),
                                      ('October', 'October'),
                                      ('November', 'November'),
                                      ('December', 'December')
                                      ], string="Billing Month", required=True)

    def send_email(self):
        self.ensure_one()
        partner_id = self.browse(self.env.context.get('active_id'))
        if partner_id:
            partner_id.write({'billing_month': self.billing_month})
        mail_template = self.env.ref('fios_connector_report.mail_template_fios_active_units', raise_if_not_found=False)
        ctx = {
            'default_model': 'res.partner',
            'default_res_id': partner_id.id,
            'default_use_template': bool(mail_template),
            'default_template_id': mail_template.id if mail_template else None,
            'default_composition_mode': 'comment',
            'default_email_layout_xmlid': 'mail.mail_notification_layout_with_responsible_signature',
            'force_email': True,
            'billing_month': self.billing_month
        }

        return {
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'mail.compose.message',
            'views': [(False, 'form')],
            'view_id': False,
            'target': 'new',
            'context': ctx,
        }

    def print_report(self):
        partner_id = self.env['res.partner'].browse(self.env.context.get('active_id'))
        if partner_id:
            partner_id.write({'billing_month': self.billing_month})
            report = partner_id.env.ref('fios_connector_report.action_report_fios_active_unit')
            return report.report_action(partner_id)
