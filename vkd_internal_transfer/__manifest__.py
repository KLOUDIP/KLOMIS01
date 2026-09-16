# -*- coding: utf-8 -*-
{
    'name': 'Internal Payment Transfer',
    'summary': 'Transfer funds between bank and cash journals with paired Send/Receive payments.',
    'description': """
Internal Payment Transfer
=======================

Restore the classic Odoo internal liquidity transfer workflow for Odoo 19.

Supported transfer scenarios
----------------------------
* Bank → Bank
* Bank → Cash
* Cash → Bank
* Cash → Cash and any other bank/cash journal pair in the same company

Key features
------------
* Transfer money between bank and cash journals
* Create a Send payment on the source journal
* Automatically create the matching Receive payment on the destination journal
* Post journal entries on both sides and reconcile the internal transfer account
* Journal dashboard shortcut and dedicated Internal Transfers menu

Availability: Odoo.sh and On Premise. Community and Enterprise (account only).
    """,
    'author': 'VK DATA ApS',
    'website': 'https://www.vkdata.dk/',
    'version': '19.0.1.0.0',
    'license': 'OPL-1',
    'category': 'Accounting/Accounting',
    'depends': ['account'],
    'data': [
        'views/account_payment_views.xml',
        'views/account_journal_dashboard_views.xml',
        'views/account_menu.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': False,
    'auto_install': False,
}
