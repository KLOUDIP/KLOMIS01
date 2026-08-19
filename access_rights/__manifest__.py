{
    'name': 'KLOUDIP Access Rights',
    'version': '19.0.2.0.0',
    'author': 'VK DATA ApS',
    'website': 'https://www.vkdata.dk/',
    'category': '',
    'summary': 'Access Rights customizations',
    'description': """Custom Access Rights""",
    'depends': [
        'base', 'mail', 'contacts', 'stock', 'sale', 'project', 'account', 'account_reports'
    ],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/menu_items.xml',
        'views/res_users_views.xml',
        'views/ir_ui_menu_views.xml',
        'views/stock_picking_views.xml',
        'views/account_report_menuitems.xml'
    ],
    'installable': True,
    "license": "OPL-1",
}