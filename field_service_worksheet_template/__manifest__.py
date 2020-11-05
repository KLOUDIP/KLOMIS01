# -*- coding: utf-8 -*-
{
    'name': 'Field Service Worksheet Templates',
    'description': '',
    'category': 'helpdesk',
    'summary': '',
    'version': '1.0',
    'author': 'Nisus Solutions(pvt) Ltd.',
    'website': 'https://www.nisus.lk',
    'data': [
        'views/project_task.xml',
        'data/ir_sequence_data.xml',
        'views/project_portal_templates.xml',
        'views/hr_expenses.xml',
        'views/worksheet_template_line_form.xml',
        'views/helpdesk_ticket.xml',
        'report/worksheet_custom_report_templates.xml',
        'report/worksheet_custom_reports.xml',
        'report/hr_expense_report.xml',
        'data/report_data.xml',
        'wizard/select_helpdesk.xml',
        'wizard/project_task.xml',
        'security/ir.model.access.csv',
        'security/field_service_worksheet_template_security.xml',
    ],
    'depends': ['project', 'industry_fsm_report','web_studio', 'industry_fsm', 'hr_expense', 'helpdesk'],
    'installable': True,
}
