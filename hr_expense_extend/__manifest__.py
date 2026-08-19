# -*- coding: utf-8 -*-
{
    'name': "Expenses Extend",

    'summary': """
        Extend Expense module with customizations""",

    'description': """
       1. Add a button into Expense lines in Expense Sheet to open the form view of Expense Line 
    """,

    'author': "VK DATA ApS",
    'website': "https://vkdata.dk",

    'category': 'Human Resources/Expenses',
    'version': '19.0.1.0.0',
    'license': 'OPL-1',
    'depends': ['hr_expense'],
    'data': [
        'views/hr_expense_views.xml'
    ],
    'license': 'OPL-1',
    'application': False,
    'installable': True,
    'auto_install': False,
}
