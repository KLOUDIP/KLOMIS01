{
    'name': 'Website Region Redirect',
    'version': '1.0.1',
    'summary': 'Redirects users to region-specific websites based on their IP location',
    'description': """
        This module enables Odoo to redirect users to different websites 
        based on their geographical location as determined by their IP address.
    """,
    'author': 'BitBrainHub',
    'category': 'Website',
    'depends': ['website'],
    'data': [
        'security/ir.model.access.csv',
        'views/website_redirect_config_views.xml',

    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'AGPL-3',
}