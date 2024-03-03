{
    'name': 'KLOUDIP Access Rights',
    'version': '1.0.3',
    'author': 'Nisus Solutions (Pvt) Ltd',
    'category': '',
    'description': """
           Custom Access Rights
        """,
    'website': 'https://www.nisus.lk',
    'depends': [
        'base', 'mail', 'contacts', 'stock', 'sale', 'project', 'account', 'account_reports'
    ],

    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/menu_items.xml',
        'views/res_users.xml',
        'views/stock_picking_views.xml',
        'views/account_report_menuitems.xml'
    ],

    'installable': True,
}