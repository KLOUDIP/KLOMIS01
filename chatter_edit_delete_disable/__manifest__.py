{
    "name": "Chatter Restrictions",
    "summary": "Remove Chatter Edit and create functionalities",
    "description": "Remove Chatter Edit and create functionalities",
    "category": "website",
    'version': '19.0.1.0.0',
    'author': "VK Data ApS",
    'website': "https://vkdata.dk",
    "depends": ['base', 'mail'],
    'assets': {
        'web.assets_backend': [
            'chatter_edit_delete_disable/static/src/embed/common/**/*',
        ],
    },
    'license': 'OPL-1',
    'application': False,
    'installable': True,
    'auto_install': False,
}
