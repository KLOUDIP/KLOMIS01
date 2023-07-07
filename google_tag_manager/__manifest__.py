{
    'name': "Google tag Manager",
    'version': "3.0.0",
    'author': "Nisus Solutions (Pvt) Ltd",
    'category': "Web",
    'summary': "Add google tag to Website",
    'description': "This module allows you to add Google tag for odoo V13",
    'license':'OPL-1',
	'website': 'http://www.nisus.lk/',
    'data': [
		'views/website_templates.xml',        
		'views/website_views.xml',
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
