{
    'name': 'Check Layout',
    'version': '1.0',
    'author': 'Nisus Solutions (Pvt) Ltd',
    'category': 'sale',
    'description': """
           Change the check layout
        """,
    'website': 'https://www.nisus.lk',
    'depends': [
        'account', 'account_accountant', 'account_check_printing', 'l10n_us_check_printing'
    ],

    'data': [
        'views/print_check_top.xml',
        'views/check_layout.xml',
    ],

    'installable': True,
}
