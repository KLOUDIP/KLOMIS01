# -*- encoding: utf-8 -*-
{
    'name': 'Odoo Web Client - Kloudip Customisations',
    'version': '19.0.1.0.0',
    'summary': 'Modify some default styling to match Kloudip branding',
    'sequence': '19',
    'category': 'Tools',
    'author': "VK DATA ApS",
    'website': "https://vkdata.dk",
    'depends': ['web_enterprise'],
    'data': [

    ],
    'assets': {
        'web._assets_primary_variables': [
            'kloudip_web_jsi/static/src/scss/variables_overriden.scss',
        ],
        'web.assets_backend': [
            'kloudip_web_jsi/static/src/js/change_logo.js',
            'kloudip_web_jsi/static/src/xml/base.xml',
        ],
        'web.webclient_bootstrap': [
            (
                "replace",
                "web_enterprise/static/src/img/mobile-icons/android-192x192.png",
                "kloudip_web_jsi/static/src/img/favicon.png",
            )
        ],
    },
    'installable': True,
    'auto_install': False,
    'application': False,
    'license': 'OPL-1',
}
