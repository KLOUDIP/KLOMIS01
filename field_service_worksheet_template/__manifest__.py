# -*- coding: utf-8 -*-
{
    'name': 'Field Service Worksheet Templates',
    'description': '',
    'category': 'helpdesk',
    'summary': '',
    'version': '15.0.1.0.8',
    'author': 'Nisus Solutions(pvt) Ltd.',
    'website': 'https://www.nisus.lk',
    'data': [
        'security/field_service_worksheet_template_security.xml',
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

    ],
    'depends': ['project', 'fleet', 'industry_fsm_report', 'web_studio', 'industry_fsm', 'industry_fsm_sale', 'hr_expense', 'helpdesk', 'helpdesk_fsm'],
    'installable': True,
}
