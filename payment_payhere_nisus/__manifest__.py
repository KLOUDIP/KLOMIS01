# -*- coding: utf-8 -*-
# Developed by Janath

{
    'name': 'Payhere Payment Acquirer',
    'category': 'Payment Gateway',
    'summary': 'Payment Acquirer: Payhere Implementation',
    'version': '1.0',
	'website': 'http://www.nisus.lk',
    'author': 'Nisus Solutions (pvt) Ltd',
    'description': """Payhere (ePay) Acquirer""",
    'depends': ['payment'],
    'data': [
        'views/payhere.xml',
        'views/payment_acquirer.xml',
        'data/payhere.xml',
    ],
	'license': 'Other proprietary',
}
