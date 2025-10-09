# semesters/threadlocal.py
import threading

_state = threading.local()

def set_view_alias(a): _state.view_alias = a
def get_view_alias():  return getattr(_state, "view_alias", None)

def set_write_alias(a): _state.write_alias = a
def get_write_alias():  return getattr(_state, "write_alias", None)

class force_write_alias:
    def __init__(self, alias): self.alias, self._prev = alias, None
    def __enter__(self): self._prev = get_write_alias(); set_write_alias(self.alias)
    def __exit__(self, *exc):  set_write_alias(self._prev)
