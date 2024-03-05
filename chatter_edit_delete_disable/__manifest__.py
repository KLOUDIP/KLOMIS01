{
    "name": "Chatter Restrictions",
    "summary": "Remove Chatter Edit and create functionalities",
    "description": "Remove Chatter Edit and create functionalities",
    "version": "1.0.2",
    "category": "website",
    "author": "Nisus Solutions (Pvt) Ltd",
    "website": "https://nisus.lk/",
    'license': 'OPL-1',
    "depends": ['base', 'mail'],
    'assets': {
        'web.assets_backend': [
            'chatter_edit_delete_disable/static/src/embed/common/**/*',
        ],
    },
    "installable": True,
}
