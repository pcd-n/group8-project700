import threading
_local = threading.local()

def set_view_alias(alias: str | None):
    _local.view_alias = alias

def get_view_alias() -> str | None:
    return getattr(_local, "view_alias", None)
