# -*- coding: utf-8 -*-
{
    'name': "Employee Contract Extend",
    'summary': """
        Implements logic to automatically set the accounting date based on the bill/invoice date""",
    'description': """
       Add custom fields in to Contract Salary information Tab 
       1. Deduction Basic
       2. Deduction Reimb
       3. Deduction Unpaid
       4. Leave
       5. Phone Bill Excess
       6. Reimb-Exp
       7. Reimb-Trav
       8. BR-Allownace-1
       9. BR-Allownace-2
       10.PAYE
    """,
    'author': "VK DATA ApS",
    'website': "https://vkdata.dk",
    'category': 'Human Resources/Contracts',
    'version': '19.0.2.0.0',
    'license': 'OPL-1',
    'depends': ['hr'],
    'data': [
        'views/hr_version_views.xml'
    ],
    'installable': True,
    'auto_install': False,
    'application': False
}