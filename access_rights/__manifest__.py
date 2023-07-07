{
    'name': 'KLOUDIP Access Rights',
    'version': '1.0.0',
    'author': 'Nisus Solutions (Pvt) Ltd',
    'category': '',
    'description': """
           Custom Access Rights
        """,
    'website': 'https://www.nisus.lk',
    'depends': [
        'base', 'mail', 'contacts', 'stock', 'sale'
    ],

    'data': [
        'security/security.xml',
        'views/menu_items.xml',
        'views/res_users.xml',
        'views/stock_picking_views.xml',
        'views/sale_views.xml'
    ],

    'installable': True,
}
