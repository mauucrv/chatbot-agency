"""
Multi-tenant context management.
Uses contextvars to thread tenant_id through async request processing.
"""
import contextvars
from typing import Optional

_current_tenant_id: contextvars.ContextVar[Optional[int]] = contextvars.ContextVar(
    "current_tenant_id", default=None
)

def set_current_tenant_id(tenant_id: int) -> None:
    _current_tenant_id.set(tenant_id)

def get_current_tenant_id() -> Optional[int]:
    return _current_tenant_id.get()

def require_tenant_id() -> int:
    tenant_id = _current_tenant_id.get()
    if tenant_id is None:
        raise RuntimeError("No tenant context set — this operation requires a tenant")
    return tenant_id
