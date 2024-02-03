# -*- coding: utf-8 -*-
{
    'name': "FSM Task from Website Appointment",
    'version': '1.0.1',
    'summary': 'Generates Field Service Tasks from Website Appointments',
    'description': """This module creates a field service task automatically whenever a new appointment is scheduled via the website.""",
    'category': 'Services/Field Service',
    'author': 'BitBrainHub',
    'depends': ['appointment', 'industry_fsm', 'calendar'],
    'data': [
            'views/appointment_type_views.xml',
            'views/calendar_views.xml',
            'views/project_task_views.xml'
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
    'maintainer': 'BitBrainHub'
}