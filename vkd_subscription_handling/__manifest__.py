{
    'name': 'Subscription Extensions',
    'version': '19.0.1.1.2',
    'category': 'Subscriptions',
    'summary': 'Allow portal users to manage their subscription products',
    'description': """
                    This module extends the sale subscription functionality to allow portal users to:
                    - View a consolidated view of their subscriptions
                    - Add new products to existing subscriptions
                    - Remove products from existing subscriptions
                    - All from a single interface
                    """,
    'author': 'VK Data ApS',
    'website': 'https://vkdata.dk',
    'depends': [
        'base',
        'sale_subscription',
        'sale',
        'website_sale_subscription',
        'portal',
        'account',
        'vkd_trazet_api',
    ],
    'data': [
        'views/product_template_views.xml',
        'views/portal_templates.xml',
        'views/sale_order_views.xml',
        'views/sale_subscription_plan_views.xml',
        'views/sale_portal_templates.xml',
        'views/trazet_services_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'vkd_subscription_handling/static/src/js/portal_subscription.js',
            'vkd_subscription_handling/static/src/js/prevent_quantity_change.js',
        ],
    },
    'license': 'OPL-1',
    'installable': True,
    'application': False,
    'auto_install': False,
}
