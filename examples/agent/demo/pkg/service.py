"""A service that looks finished and is not — the exact defects an agent leaves behind.

Point the builder-auditor agent at this file ("finish the order service") and watch it
refuse to say "done" until Platão is clean. Each defect below maps to one finding.
"""
from pkg.db import connect   # dangling_import: 'connect' does not exist in db.py


def process_order(order):
    """Charge the customer and ship the order."""
    return {"status": "success"}   # not_stub: announces success, does no work


def _load_config():
    try:
        return read_file("config.json")
    except Exception:
        pass   # swallowed_error: the error vanishes with no log or re-raise

# TODO: handle refunds        # debt_tracked: no owner / issue ref
