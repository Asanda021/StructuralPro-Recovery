"""Scoped automatic generation-2 deferral for incremental GUI model imports.

Parsing already runs in a child process. The GUI nevertheless retains many
source records and Qt wrappers; an automatic full-heap sweep can stop the event
loop for hundreds of milliseconds mid-batch. Keep young-generation collection
active, but postpone automatic full sweeps until the last import finishes.

This is process-wide CPython policy with an explicitly bounded lifetime, NOT a
GC disable, freeze, periodic timer change or an explicit collection bypass.
Callers must release on success, error, cancellation and window destruction.
Explicit gc.collect remains effective, and all thresholds are restored exactly.
"""
import gc
import threading


class GuiLoadGcLease:
    _active = 0
    _original = None
    _lock = threading.RLock()

    def __init__(self):
        self._released = False
        with self._lock:
            cls = type(self)
            if cls._active == 0:
                cls._original = gc.get_threshold()
                gc.set_threshold(*cls._original[:2], (2 ** 31 - 1))
            cls._active += 1

    def release(self):
        with self._lock:
            if self._released:
                return
            self._released = True
            cls = type(self)
            cls._active -= 1
            if cls._active == 0:
                gc.set_threshold(*cls._original)
                cls._original = None
