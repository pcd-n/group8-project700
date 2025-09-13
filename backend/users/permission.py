"""
Custom permission classes for role-based access control.
Based on actual roles in the system: Admin, Coordinator, Tutor, Support, Member
"""
from rest_framework.permissions import BasePermission
from .models import User, Role


class BaseRolePermission(BasePermission):
    """Base class for role-based permissions."""
    
    required_roles = []  # Override in subclasses
    
    def has_permission(self, request, view):
        """Check if user has required role."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Staff users can bypass role checks
        if request.user.is_staff:
            return True
        
        # Check if user has any of the required roles
        user_role = request.user.get_active_role()
        if not user_role:
            return False
        
        return user_role.role_name in self.required_roles
    
    def has_object_permission(self, request, view, obj):
        """Object-level permission check."""
        # Default to basic permission check
        return self.has_permission(request, view)


class IsAdminUser(BaseRolePermission):
    """Permission class for Admin users only."""
    
    required_roles = ['Admin']
    
    def has_permission(self, request, view):
        """Admin users have full access."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        return (request.user.is_staff or 
                request.user.has_role('Admin'))


class IsCoordinatorUser(BaseRolePermission):
    """Permission class for Coordinator users."""
    
    required_roles = ['Coordinator', 'Admin']


class IsTutorUser(BaseRolePermission):
    """Permission class for Tutor users."""
    
    required_roles = ['Tutor', 'Coordinator', 'Admin']


class IsSupportUser(BaseRolePermission):
    """Permission class for Support users."""
    
    required_roles = ['Support', 'Admin']


class IsMemberUser(BaseRolePermission):
    """Permission class for Member users (default role)."""
    
    required_roles = ['Member', 'Tutor', 'Coordinator', 'Support', 'Admin']


class IsStaffOrOwner(BasePermission):
    """Permission class allowing staff users or object owners."""
    
    def has_permission(self, request, view):
        """Basic authentication check."""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Allow staff or object owner."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Staff/Admin users can access everything
        if request.user.is_staff or request.user.has_role('Admin'):
            return True
        
        # Check if user is the owner of the object
        if hasattr(obj, 'user'):
            return obj.user == request.user
        elif hasattr(obj, 'owner'):
            return obj.owner == request.user
        elif isinstance(obj, User):
            return obj == request.user
        
        return False


class IsAdminOrCoordinator(BaseRolePermission):
    """Permission class for Admin or Coordinator users."""
    
    required_roles = ['Admin', 'Coordinator']


class IsStaffLevel(BaseRolePermission):
    """Permission class for staff-level users (Admin, Coordinator, Support)."""
    
    required_roles = ['Admin', 'Coordinator', 'Support']


class IsTeachingStaff(BaseRolePermission):
    """Permission class for teaching staff (Coordinators, Tutors)."""
    
    required_roles = ['Admin', 'Coordinator', 'Tutor']


class CanManageUsers(BasePermission):
    """
    Permission for user management operations.
    Only Admin and Coordinator can manage users.
    """
    
    def has_permission(self, request, view):
        """Check if user can manage other users."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Only Admin and Coordinator can manage users
        if request.user.is_staff or request.user.has_role('Admin'):
            return True
        
        # Coordinators can manage users
        if request.user.has_role('Coordinator'):
            return True
        
        return False
    
    def has_object_permission(self, request, view, obj):
        """Object-level permission for user management."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin users can manage all users
        if request.user.is_staff or request.user.has_role('Admin'):
            return True
        
        # Users can manage themselves
        if isinstance(obj, User) and obj == request.user:
            return True
        
        # Coordinators can manage tutors and members
        if request.user.has_role('Coordinator'):
            if isinstance(obj, User):
                target_role = obj.get_active_role_name()
                return target_role in ['Tutor', 'Member']
        
        return False


class CanManageRoles(BasePermission):
    """Permission for role management operations - Admin only."""
    
    def has_permission(self, request, view):
        """Only Admin users can manage roles."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        return (request.user.is_staff or 
                request.user.has_role('Admin'))


class CanAssignRoles(BasePermission):
    """Permission for role assignment operations."""
    
    def has_permission(self, request, view):
        """Check if user can assign roles."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin users can assign any role
        if request.user.is_staff or request.user.has_role('Admin'):
            return True
        
        # Coordinators can assign limited roles
        if request.user.has_role('Coordinator'):
            return True
        
        return False
    
    def has_object_permission(self, request, view, obj):
        """Object-level permission for role assignment."""
        if not self.has_permission(request, view):
            return False
        
        # Admin can assign any role to anyone
        if request.user.is_staff or request.user.has_role('Admin'):
            return True
        
        # Coordinators can only assign Tutor and Member roles
        if request.user.has_role('Coordinator'):
            # Check the role being assigned from request data
            role_data = getattr(request, 'data', {})
            if isinstance(role_data, list):
                # Bulk assignment
                allowed_roles = ['Tutor', 'Member']
                for item in role_data:
                    role_id = item.get('role_id')
                    if role_id:
                        try:
                            role = Role.objects.get(id=role_id)
                            if role.role_name not in allowed_roles:
                                return False
                        except Role.DoesNotExist:
                            return False
            else:
                # Single assignment
                role_id = role_data.get('role_id')
                if role_id:
                    try:
                        role = Role.objects.get(id=role_id)
                        return role.role_name in ['Tutor', 'Member']
                    except Role.DoesNotExist:
                        return False
        
        return True


class CanViewUserProfile(BasePermission):
    """Permission for viewing user profiles."""
    
    def has_permission(self, request, view):
        """Basic authentication check."""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Check if user can view specific profile."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin and staff can view all profiles
        if request.user.is_staff or request.user.has_role('Admin'):
            return True
        
        # Users can view their own profile
        if isinstance(obj, User) and obj == request.user:
            return True
        
        # Coordinators can view tutor and member profiles
        if request.user.has_role('Coordinator'):
            if isinstance(obj, User):
                target_role = obj.get_active_role_name()
                return target_role in ['Tutor', 'Member']
        
        # Support can view all profiles
        if request.user.has_role('Support'):
            return True
        
        # Tutors can view member profiles
        if request.user.has_role('Tutor'):
            if isinstance(obj, User):
                target_role = obj.get_active_role_name()
                return target_role in ['Member']
        
        return False


class ReadOnlyForMembers(BasePermission):
    """Allow read-only access for members, full access for staff."""
    
    def has_permission(self, request, view):
        """Check basic permission."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin and staff have full access
        user_role = request.user.get_active_role_name()
        if user_role in ['Admin', 'Coordinator', 'Tutor', 'Support'] or request.user.is_staff:
            return True
        
        # Members have read-only access
        if user_role == 'Member':
            return request.method in ['GET', 'HEAD', 'OPTIONS']
        
        return False


class AdminOrCoordinatorOnly(BasePermission):
    """
    Restrict bulk operations and user listing to Admin and Coordinator only.
    As specified: bulk update, list all users can only be done by Admin and coordinator.
    """
    
    def has_permission(self, request, view):
        """Only Admin and Coordinator can perform these operations."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Only Admin and Coordinator allowed
        if request.user.is_staff or request.user.has_role('Admin'):
            return True
        
        if request.user.has_role('Coordinator'):
            return True
        
        return False


class CanCreateEOI(BasePermission):
    """Permission for EOI creation - Admin and Support only."""
    
    def has_permission(self, request, view):
        """Check if user can create EOIs."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        user_role = request.user.get_active_role_name()
        return (request.user.is_staff or 
                user_role in ['Admin', 'Support'])


class CanManageAllocations(BasePermission):
    """Permission for allocation management - Admin and Coordinator."""
    
    def has_permission(self, request, view):
        """Check if user can manage allocations."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        user_role = request.user.get_active_role_name()
        return (request.user.is_staff or 
                user_role in ['Admin', 'Coordinator'])


class CanViewAudit(BasePermission):
    """Permission for viewing audit trail - Admin and Support only."""
    
    def has_permission(self, request, view):
        """Check if user can view audit trail."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        user_role = request.user.get_active_role_name()
        return (request.user.is_staff or 
                user_role in ['Admin', 'Support'])


class CustomPermissionMixin:
    """Mixin to add custom permission checking methods to views."""
    
    def check_custom_permission(self, permission_key):
        """Check if current user has specific custom permission."""
        if not self.request.user or not self.request.user.is_authenticated:
            return False
        
        # Staff users bypass custom permission checks
        if self.request.user.is_staff:
            return True
        
        return self.request.user.has_custom_permission(permission_key)
    
    def require_role(self, *roles):
        """Decorator-like method to require specific roles."""
        def decorator(func):
            def wrapper(*args, **kwargs):
                user_role = self.request.user.get_active_role_name()
                if user_role not in roles and not self.request.user.is_staff:
                    from rest_framework.exceptions import PermissionDenied
                    raise PermissionDenied("Insufficient role permissions")
                return func(*args, **kwargs)
            return wrapper
        return decorator


# Convenience permission combinations
class AdminOnlyPermission(IsAdminUser):
    """Alias for IsAdminUser for clarity."""
    pass


class CoordinatorPermission(IsAdminOrCoordinator):
    """Alias for IsAdminOrCoordinator for clarity."""
    pass


class StaffLevelPermission(IsStaffLevel):
    """Permission for staff-level access."""
    pass


class TeachingStaffPermission(IsTeachingStaff):
    """Alias for IsTeachingStaff for clarity."""
    pass


class MemberAccessPermission(IsMemberUser):
    """Permission for member-level access."""
    pass