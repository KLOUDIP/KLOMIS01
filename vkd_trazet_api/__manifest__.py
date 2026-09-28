{
    'name': "Trazet API",
    'summary': "Integration between Odoo and Trazet platform",
    'description': """
        Provides:
        - User synchronization with Trazet
        - Automatic login functionality
        - API endpoints for Trazet integration
    """,
    'author': 'VK DATA ApS',
    'website': 'https://vkdata.dk/',
    'category': 'Hidden',
    'version': '19.0.1.0.6',
    'license': 'OPL-1',
    'depends': ['base', 'product', 'sale', 'sale_subscription', 'account_accountant'],
    'data': [
        'security/ir.model.access.csv',
        'data/ir_config_parameter.xml',
        'views/res_user_views.xml',
        'views/res_partner_views.xml',
        'views/product_template_views.xml',
        'views/sale_order_views.xml',
        'views/api_retry_log_views.xml',
        'data/ir_cron_data.xml',
    ],
    'external_dependencies': {
        'python': ['PyJWT'],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
}
