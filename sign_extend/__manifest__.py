# -*- coding: utf-8 -*-
{
    'name': 'Sign Remove Logo',
    'version': '1.0.1',
    'summary': 'Removes Logo from Sign Module',
    'description': """
    Sign Remove Logo
================
This module customizes the Odoo Sign module to remove the logo from the document sign page.
""",
    'category': 'Tools',
    "author": "BitbrainHub",
    "email": "bitbrainhub@gmail.com",
    'depends': ['sign'],
    'data': [
        'views/sign_request_templates.xml'
    ],
    'demo': [],
    'qweb': [],
    'installable': True,
    'application': True,
    'auto_install': False,
    'licence': 'LGPL-3',
}
