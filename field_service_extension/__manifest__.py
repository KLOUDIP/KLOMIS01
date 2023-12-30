# -*- coding: utf-8 -*-
{
    'name': 'FieldService Extension',
    "summary": "This module allow to add v13 features to v14",
    "description": "This module allow to add v13 features to v14",
    'category': 'Operations/Field Service',
    'version': '1.0.2',
    "author": "Nisus Solutions (Pvt) Ltd",
    "website": "https://nisus.lk/",
    'data': [
        'views/project_views.xml',
        'security/fsm_security.xml',
        'security/ir.model.access.csv',
        'views/menus.xml'
    ],
    'depends': ['industry_fsm', 'project', 'project_enterprise'],
}
