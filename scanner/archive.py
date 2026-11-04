"""Deployment archive. Library tests stay usable; the running services do not scan or pay."""

import os

NOTICE = "Projekt archiviert. Keine automatischen Scans und keine bezahlten Datenabrufe."


def paid_network_closed() -> bool:
    """True only in a container that was started with SCANNER_ARCHIVED=1."""
    return os.environ.get("SCANNER_ARCHIVED") == "1"
