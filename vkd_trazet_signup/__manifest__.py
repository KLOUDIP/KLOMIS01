{
    'name': "Trazet Signup",
    'summary': "Public sign-up page on the Odoo website that registers new accounts on Trazet",
    'description': """
        Provides a public page (/trazet-signup) where prospects sign up for Trazet
        directly from the Odoo website. same as the current flow - this module does not create
        Odoo users itself. On success the visitor is redirected to Trazet.

        Also blocks buying Trazet-linked products (trazet_product_key set) for visitors
        without a Trazet account: adding one to the cart or reaching checkout redirects
        them to the sign-up page instead.
    """,
    'author': 'VK DATA ApS',
    'website': 'https://vkdata.dk/',
    'category': 'Website',
    'version': '19.0.1.1.0',
    'license': 'OPL-1',
    'depends': ['website', 'website_sale', 'vkd_trazet_api'],
    'data': [
        'data/ir_config_parameter.xml',
        'views/trazet_signup_templates.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'vkd_trazet_signup/static/src/js/cart_service_patch.js',
            'vkd_trazet_signup/static/src/js/signup_form.js',
            'vkd_trazet_signup/static/src/css/signup_form.css',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
}