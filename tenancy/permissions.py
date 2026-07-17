# tenancy/permissions.py
from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Membership, ROLE_RANK, Role


def user_max_role(user, organization=None) -> str | None:
    """Highest role a user holds (optionally within one organization)."""
    if not user or not user.is_authenticated:
        return None
    if getattr(user, "is_superuser", False):
        return Role.ADMIN
    qs = Membership.objects.filter(user=user)
    if organization is not None:
        qs = qs.filter(organization=organization)
    roles = [m.role for m in qs]
    if not roles:
        return None
    return max(roles, key=lambda r: ROLE_RANK.get(r, 0))


def _rank(role: str | None) -> int:
    return ROLE_RANK.get(role, 0)


class HasMinimumRole(BasePermission):
    """Require at least ``required_role`` (view attribute) in any org.

    Default policy if a view sets no ``required_role``:
      - safe methods (GET/HEAD/OPTIONS): viewer+
      - writes: developer+
    Views can override with ``required_role = Role.OPERATOR`` etc.
    """

    def has_permission(self, request, view) -> bool:
        required = getattr(view, "required_role", None)
        if required is None:
            required = Role.VIEWER if request.method in SAFE_METHODS else Role.DEVELOPER
        return _rank(user_max_role(request.user)) >= _rank(required)


def require_role(required_role: str):
    """Factory for a permission class enforcing a specific minimum role."""

    class _RoleRequired(HasMinimumRole):
        def has_permission(self, request, view) -> bool:
            return _rank(user_max_role(request.user)) >= _rank(required_role)

    _RoleRequired.__name__ = f"RoleRequired_{required_role}"
    return _RoleRequired


IsViewer = require_role(Role.VIEWER)
IsDeveloper = require_role(Role.DEVELOPER)
IsOperator = require_role(Role.OPERATOR)
IsAdmin = require_role(Role.ADMIN)
