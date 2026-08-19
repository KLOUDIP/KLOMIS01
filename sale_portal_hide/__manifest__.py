# Copyright (C) 2021 TREVI Software
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Website Hide Sales Orders and Quotations",
    'version': '19.0.1.0.0',
    'license': 'OPL-1',
    "author": """TREVI Software,
        Odoo Community Association (OCA)""",
    "summary": """Hide orders &amp; quotations in the customer portal.""",
    "description": "Hide sales orders and quotations in the customer portal home page.",
    "category": "Sales",
    "maintainers": ["TREVI Software"],
    "images": ["static/src/img/main_screenshot.png"],
    'author': "VK Data ApS",
    'website': "https://vkdata.dk",
    "depends": [
        "portal",
        "sale",
    ],
    "data": [
        "views/sale_portal_templates.xml",
    ],
    'license': 'OPL-1',
    'application': False,
    'installable': True,
    'auto_install': False,
}
