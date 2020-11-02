{
    'name': "Google tag Manager",
    'version': "1.0",
    'author': "Nisus Solutions (Pvt) Ltd",
    'category': "Web",
    'summary': "Add google tag to Website",
    'description': "This module allows you to add Google tag for odoo V12",
    'license':'LGPL-3',
    'website': 'http://www.nisus.lk/',
    'data': [
        'views/form.xml',
        'views/template.xml',
        'views/res_config_settings_views.xml',
    ],
    'demo': [],
    'images':[
        'static/description/icon.png',
    ],
    'price': 0.00,
    'currency': 'USD',
    'depends': ['website'],
    'installable': True,
}
