# -*- coding: utf-8 -*-

{
    'name': 'Product Configurator Sale Extension',
    'category': 'Product Configurator',
    'summary': 'Product Configurator Sale Extend Plugin',
    'version': '1.0.7',
    'website': 'http://www.nisus.lk',
    'author': 'Nisus Solutions(PVT) Ltd.',
    'description': """This module will extend the Product Configurator Sale module with more options.""",
    'depends': ['product_configurator', 'product_configurator_sale', 'sale_product_configurator'],
    'data': [
        'security/ir.model.access.csv',
        'wizards/mandatory_alternative_products_view.xml',
        'views/product_product_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
}