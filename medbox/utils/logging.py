"""Logging structuré avec tenant_id."""

import logging
from typing import NamedTuple


class AuditLog(NamedTuple):
    """Données d'audit pour log_audit."""

    action: str
    tenant_id: str
    user_id: str
    resource: str
    status: str = "success"
    details: dict | None = None


class TenantLogFormatter(logging.Formatter):
    """Formatter structuré incluant tenant_id dans tous les logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Format le log avec tenant_id."""
        if hasattr(record, "tenant_id"):
            return (
                f"{record.asctime} - {record.name} - {record.levelname} - "
                f"[{record.tenant_id}] - {record.getMessage()}"
            )
        return super().format(record)


def setup_tenant_logging(
    log_level: str = "INFO",
    log_file: str | None = None,
) -> None:
    """Configure le logging structuré avec tenant_id.

    Parameters
    ----------
    log_level : str
        Niveau de log (DEBUG, INFO, WARNING, ERROR)
    log_file : str | None
        Path du fichier de log. Si None, logs en stdout uniquement.

    """
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Handler console
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    formatter = TenantLogFormatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Handler fichier si spécifié
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(log_level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)


LOGGER = logging.getLogger(__name__)


def log_audit(audit_log: AuditLog) -> None:
    """Log standardisé pour audit trail.

    Parameters
    ----------
    audit_log : AuditLog
        Données d'audit (action, tenant_id, user_id, resource, status, details)

    """
    LOGGER.info(
        "%s %s",
        audit_log.action,
        audit_log.resource,
        extra={
            "tenant_id": audit_log.tenant_id,
            "user_id": audit_log.user_id,
            "action": audit_log.action,
            "resource": audit_log.resource,
            "status": audit_log.status,
            "details": audit_log.details,
        },
    )
