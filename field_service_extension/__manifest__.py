# -*- coding: utf-8 -*-
{
    'name': 'FieldService Extension',
    "summary": "This module allow to add v13 features to v14",
    "description": "This module allow to add v13 features to v14",
    'category': 'Operations/Field Service',
    'version': '19.0.1.0.0',
    'author': "VK Data ApS",
    'website': "https://vkdata.dk",
    'data': [
        'views/project_views.xml',
        'security/fsm_security.xml',
        'security/ir.model.access.csv',
        'views/menus.xml'
    ],
    'depends': ['industry_fsm', 'project', 'project_enterprise', 'field_service_worksheet_template'],
    'license': 'OPL-1',
    'application': False,
    'installable': True,
    'auto_install': False,
}
