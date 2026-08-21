{
    'name': 'KloudIP - Stock Extend ',
    'version': '19.0.1.0.3',
    'summary': 'KloudIP Inventory (Stock) Customizations',
    'sequence': '20',
    'category': 'Inventory',
    'author': "VK DATA ApS",
    'website': "https://vkdata.dk",
    'data': [
        'data/server_actions.xml',
        'views/production_lot_views.xml',
    ],
    # sale_stock: stock_picking.py overrides its _compute_sale_id.
    'depends': ['base', 'stock', 'sale_stock'],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'OPL-1',
}
