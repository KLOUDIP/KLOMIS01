# -*- coding: utf-8 -*-
{
    'name': 'Sale Order Task Type',
    "summary": "This module allow to add task type to sale order, delivery order and invoice",
    "description": "This module allow to add task type to sale order, delivery order and invoice",
    'category': 'sale',
    'version': '1.0.1',
    "author": "Nisus Solutions (Pvt) Ltd",
    "website": "https://nisus.lk/",
    'data': [
        'views/sale_order_views.xml',
        'views/stock_picking_views.xml',
        'views/account_invoice_view.xml',
        'report/stock_report_deliveryslip.xml',
        'report/report_invoice.xml',
    ],
    'depends': ['sale', 'project', 'stock'],
}
