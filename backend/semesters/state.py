# semesters/state.py
import contextvars
_current_alias = contextvars.ContextVar("semester_alias", default=None)

def set_current_alias(alias): _current_alias.set(alias)
def get_current_alias(): return _current_alias.get()
