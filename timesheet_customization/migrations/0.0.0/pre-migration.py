import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    cr.execute("delete from project_task where project_id is null and parent_id is not null;")
    _logger.info("Deleted tasks")
