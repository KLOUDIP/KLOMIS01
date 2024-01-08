# -*- encoding: utf-8 -*-
{
    'name': 'FIOS Connector Active Unit Report',
    'summary': """This module allow to print the FIOS active units report""",
    'description': """This module allow to print the FIOS active units report""",
    'version': '1.0.1',
    'category': 'Fleet',
    'author': 'Ranga Dharmapriya',
    'website': '',
    'depends': ['fios_connector'],
    'data': [
        'security/ir.model.access.csv',
        'reports/ir_actions_report.xml',
        'reports/ir_actions_report_templates.xml',
        'data/mail_template_data.xml',
        'wizard/fios_unit_report_wizard.xml'
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
