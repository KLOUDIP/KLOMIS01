# -*- coding: utf-8 -*-
{
    'name': 'Sign Remove Logo',
    'version': '19.0.1.0.0',
    'summary': 'Removes Logo from Sign Module',
    'description': """
    Sign Remove Logo
================
This module customizes the Odoo Sign module to remove the logo from the document sign page.
""",
    'category': 'Tools',
    'author': "VK Data ApS",
    'website': "https://vkdata.dk",
    'depends': ['sign'],
    'data': [
        'views/sign_request_templates.xml'
    ],
    'demo': [],
    'qweb': [],
    'license': 'OPL-1',
    'application': False,
    'installable': True,
    'auto_install': False,
}
