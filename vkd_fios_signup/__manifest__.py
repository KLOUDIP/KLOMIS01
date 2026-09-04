# -*- coding: utf-8 -*-
{
    'name': "Trazet FIOS Signup",
    'summary': "Public sign-up page that provisions a FIOS customer account",
    'description': """
        Provides a public page (/fios-signup) where a prospect signs up for FIOS.
        On submit it finds-or-creates an Odoo partner + portal user (marking them
        is_fios_user without disturbing any existing is_trazet_user status) and
        runs the FIOS provisioning flow (create user -> resource -> account).
    """,
    'author': 'VK DATA ApS',
    'website': 'https://vkdata.dk/',
    'category': 'Website',
    'version': '19.0.2.3.0',
    'license': 'OPL-1',
    'depends': ['website', 'website_sale', 'portal', 'vkd_fios_api'],
    'data': [
        'views/fios_signup_templates.xml',
        'views/portal_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'vkd_fios_signup/static/src/js/cart_service_patch.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}