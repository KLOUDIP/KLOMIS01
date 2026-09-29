{
    "name": "Task Status Access",
    "version": "19.0.1.0.0",
    "summary": "Only the Manager group can change Task Status on tasks",
    "description": "Only the 'Task Status Manager' group can change Task Status (Ontime / Late / Priority) on tasks",
    "category": "Services/Project",
    'author': 'VK DATA ApS',
    'website': 'https://www.vkdata.dk/',
    "license": "OPL-1",
    "depends": ["project", "field_service_worksheet_template"],
    "data": [
        "security/vkd_task_status_security.xml",
    ],
    "installable": True,
    "application": False,
}
