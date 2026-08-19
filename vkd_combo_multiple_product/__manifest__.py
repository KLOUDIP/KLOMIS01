# -*- coding: utf-8 -*-
{
    'name': 'Combo Multiple Product',
    'description': """Extends product combo functionality with multiple quantities and recurring pricing. 
                   Allows combo items to have custom quantities and subscription-based pricing for
                   enhanced bundling capabilities.""",
    'summary': 'Enhanced product combos with multiple quantities and subscription pricing support',
    'category': 'Sales',
    'version': "19.0.1.0.0",
    'author': 'VK DATA ApS',
    'website': 'https://vkdata.dk',
    'depends': ['base','product', 'website_sale', 'sale','account','sale_subscription'],
    'data': [
        'security/ir.model.access.csv',
        'views/combo_item_recurring_price_views.xml',
        'views/product_combo_views.xml',
    ],

    'license': 'OPL-1',
    'installable': True,
    'application': False,
    'auto_install': False,
}
