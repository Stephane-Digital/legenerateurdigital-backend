
from typing import Dict, Any
from datetime import datetime


def log_systeme_event(data: Dict[str, Any]):
    """
    Logger simple pour les actions Systeme.io
    Peut être remplacé plus tard par une table SQL
    """

    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        **data
    }

    print("[LGD SYSTEME.IO LOG]", log_entry)
