"""Singleton pattern.

Any class that uses SingletonMeta as its metaclass has exactly one instance.
The first call to the class creates the instance. Every later call returns
that same object.

FastAPI handles requests on several threads, so creation is guarded by a lock.
The lock is re-entrant because one singleton can create another while it is
being built (DatabaseManager reads Settings in its constructor).
"""
import threading
from typing import Any


class SingletonMeta(type):
    _instances: dict[type, Any] = {}
    _lock = threading.RLock()

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        # Check once without the lock so normal calls stay fast, then check
        # again inside it so two threads cannot both create an instance.
        if cls not in SingletonMeta._instances:
            with SingletonMeta._lock:
                if cls not in SingletonMeta._instances:
                    SingletonMeta._instances[cls] = super().__call__(*args, **kwargs)
        return SingletonMeta._instances[cls]
