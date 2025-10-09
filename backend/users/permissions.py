# backend/users/permissions.py
from rest_framework.permissions import BasePermission, SAFE_METHODS

# Helper to avoid repeated DB hits; your User helpers already pin to default DB.
def role_name(user):
    return getattr(user, "get_active_role_name", lambda: None)() if user and user.is_authenticated else None

class IsAuthenticatedAndHasRole(BasePermission):
    required_roles = ()  # override per subclass

    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        # Staff bypass = treat as admin
        if request.user.is_staff:
            return True
        rn = role_name(request.user)
        return rn in self.required_roles if self.required_roles else True


# ---- Three-role gates --------------------------------------------------------

class IsAdminRole(IsAuthenticatedAndHasRole):
    required_roles = ("Admin",)

class IsCoordinatorRole(IsAuthenticatedAndHasRole):
    required_roles = ("Coordinator", "Admin")

class IsTutorRole(IsAuthenticatedAndHasRole):
    required_roles = ("Tutor", "Coordinator", "Admin")

class IsAdminOrCoordinator(IsAuthenticatedAndHasRole):
    required_roles = ("Admin", "Coordinator")


# ---- Composable behavior guards ----------------------------------------------

class TutorReadOnly(BasePermission):
    """
    Tutors may only perform SAFE_METHODS.
    Admin/Coordinator unaffected.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        rn = role_name(request.user)
        if rn == "Tutor":
            return request.method in SAFE_METHODS
        return True


class IsStaffOrOwner(BasePermission):
    """
    Allow staff/admin or the object owner.
    Ownership is resolved via `obj.user` or `obj.owner`, or the object itself if it's a User.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff or role_name(request.user) == "Admin":
            return True

        # Common ownership patterns
        if hasattr(obj, "user"):
            return obj.user == request.user
        if hasattr(obj, "owner"):
            return obj.owner == request.user
        # Direct user object
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            if isinstance(obj, User):
                return obj == request.user
        except Exception:
            pass
        return False


# ---- App-specific policy for your requirements -------------------------------

class CanManageUsers(BasePermission):
    """
    Only Admin can manage users (create/list/update/delete/reset).
    Non-admins can still manage themselves (profile/password changes) where views allow it.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff or role_name(request.user) == "Admin":
            return True
        # Non-admins: let the view do object-level checks for self-service endpoints
        # but block collection-level management (e.g., POST /users/, GET /users/)
        # A simple convention: disallow non-admin on non-safe or collection ops
        return False

    def has_object_permission(self, request, view, obj):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff or role_name(request.user) == "Admin":
            return True
        # Self-management (e.g., /api/me/...) allowed via dedicated endpoints, not here
        return False


class CanManageAllocations(BasePermission):
    """
    Admin and Coordinator can allocate tutors and edit allocation-related data.
    Tutors are not allowed.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        rn = role_name(request.user)
        return rn in ("Admin", "Coordinator")


class CanSetPreferences(BasePermission):
    """
    Admin and Coordinator can set EOI/preference values.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.user.is_staff:
            return True
        rn = role_name(request.user)
        return rn in ("Admin", "Coordinator")
