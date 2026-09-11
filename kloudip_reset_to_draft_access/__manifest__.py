{
    'name': 'Accounting: Reset to Draft Access',
    'version': '19.0.1.0.0',
    'author': 'VK DATA ApS',
    'website': 'https://www.vkdata.dk/',
    'summary': 'Dedicated group allowing selected users to reset posted entries to draft',
    'description': """
Odoo blocks resetting a reviewed/posted entry to draft with
"Validated entries can only be changed by your accountant." unless the user
passes account.move._is_user_able_to_review().

This module adds a dedicated group so that specific users can be granted that
right without being given the full Accounting Administrator role and without
any Settings/administration access.

NOTE ON 'depends': account_accountant is listed so that this module is loaded
AFTER it. account_accountant overrides _is_user_able_to_review(); if this
module loaded first, its override would sit lower in the MRO and never run.
On a Community database without account_accountant, remove it from depends.
""",
    'category': 'Accounting/Accounting',
    'depends': ['account', 'account_accountant'],
    'data': [
        'security/reset_to_draft_security.xml',
    ],
    'license': 'OPL-1',
    'installable': True,
    'auto_install': False,
}
