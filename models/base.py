"""Compatibility shim for LGD models.

Some parts of the codebase expect `from models import Base` or `from models.base import Base`.
We re-export the SQLAlchemy Base from database.py.
"""

from database import Base  # noqa: F401
