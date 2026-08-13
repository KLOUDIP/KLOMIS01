{
    'name': "Sri Lankan Tax Invoice Report",
    'version': '17.0.1.2.9',
    'category': 'Accounting',
    'summary': 'Sri Lankan Tax Invoice Report Customization',
    'description': """
        This module adds Sri Lankan tax invoice format support.
        - Adds boolean field to identify Sri Lankan taxable journals
        - Customizes invoice report for Sri Lankan tax invoices
        - Maintains standard format for non-Sri Lankan journals
    """,
    'author': "VK Data ApS",
    'website': "https://vkdata.dk",
    'depends': ['base', 'account'],
    'data': [
        'views/account_journal_views.xml',
        'views/account_move_views.xml',
        'report/report_template.xml',
    ],
    'assets': {
        'web.report_assets_common': [
            'vkd_lk_account_tax_report/static/src/css/report_styles.css',
        ],
    },
    'demo': [
    ],
    'licence': 'OPL-1',
    'application': False,
    'installable': True,
    'auto_install': False,

}
