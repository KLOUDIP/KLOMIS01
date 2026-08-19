{
    'name': 'Check Layout',
    'version': '19.0.2.0.0',
    'author': 'VK DATA ApS',
    'website': 'https://www.vkdata.dk/',
    'category': 'Sales',
    'summary': 'Check Layout customizations',
    'description': """This module is used to change the check layout""",
    'depends': [
        'account', 'account_accountant', 'account_check_printing', 'l10n_us_check_printing'
    ],
    'data': [
        'views/print_check_top.xml',
        'views/check_layout.xml',
    ],
    'installable': True,
    "license": "OPL-1",
}
