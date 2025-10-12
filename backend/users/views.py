# backend/users/views.py
from django.shortcuts import render
from django.db.models import Q
from rest_framework import status, generics, serializers
from rest_framework.permissions import AllowAny, IsAuthenticated, BasePermission
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.db import IntegrityError
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from django.contrib.auth import authenticate
from django.db import transaction, connections
from drf_spectacular.utils import extend_schema, OpenApiExample
from .models import User, Role, Permission, UserRoles, Supervisor, Campus
from .serializers import (
    UserSerializer, UserCreateSerializer, UserUpdateSerializer,
    RoleSerializer, PermissionSerializer, UserRolesSerializer,
    SupervisorSerializer
)
from .permissions import (
    IsAdminRole, IsAdminOrCoordinator, TutorReadOnly,
    CanManageAllocations, CanSetPreferences,
)
from semesters.services import get_active_semester_alias
from rich.console import Console
import logging

DEFAULT_DB = "default"
# Configure rich console
console = Console()
logger = logging.getLogger(__name__)

@api_view(["GET"])
@permission_classes([IsAdminRole])
def eoi_tutor_emails(request):
    """
    GET /api/tutors/eoi-emails/?alias=sem_2025_s2
    Returns list of {email, first_name, last_name} from the alias DB (EOI upload).
    """
    alias = request.GET.get("alias") or get_active_semester_alias()
    if not alias:
        return Response({"detail": "No active semester alias."}, status=400)

    # some old aliases might not have username column; safe to ignore
    # only pick rows that have an email (uploaded EOI tutors)
    qs = User.objects.using(alias).filter(email__isnull=False).exclude(email="").values(
        "email", "first_name", "last_name"
    )
    # de-dupe + normalise case
    seen, data = set(), []
    for r in qs:
        email = (r["email"] or "").strip().lower()
        if not email or email in seen:
            continue
        seen.add(email)
        data.append({
            "email": email,
            "first_name": (r["first_name"] or "").strip(),
            "last_name":  (r["last_name"]  or "").strip(),
        })
    return Response(data, status=200)

@api_view(["GET"])
@permission_classes([IsAdminRole])
def roles_list(request):
    roles = Role.objects.using(DEFAULT_DB).all().order_by("role_name")
    data = RoleSerializer(roles, many=True).data
    return Response(data) 

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    from django.contrib.auth import logout as django_logout
    django_logout(request)
    resp = Response(status=204)
    resp.delete_cookie('access'); resp.delete_cookie('refresh')
    return resp

def _ensure_alias_username_column(alias: str):
    if not alias or alias == DEFAULT_DB:
        return
    with connections[alias].cursor() as c:
        c.execute("SHOW COLUMNS FROM `users_user` LIKE 'username'")
        has = c.fetchone() is not None
        if not has:
            # Minimal compatible field spec with your current User model
            c.execute("ALTER TABLE `users_user` ADD COLUMN `username` varchar(150) DEFAULT ''")
            c.execute("CREATE UNIQUE INDEX IF NOT EXISTS users_user_username_uniq ON `users_user` (`username`)")

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(help_text="User's username")
    password = serializers.CharField(write_only=True, help_text="User's password")

class LoginResponseSerializer(serializers.Serializer):
    """Serializer for login response."""
    user = UserSerializer()
    tokens = serializers.DictField(help_text="JWT access and refresh tokens")


class LoginView(generics.CreateAPIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    @extend_schema(
        request=LoginSerializer,
        responses={200: dict},
        examples=[OpenApiExample('Login', value={'username': 'admin', 'password': 'abcabc'})],
    )
    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = authenticate(
            request,
            username=s.validated_data["username"],
            password=s.validated_data["password"],
        )
        if not user:
            return Response({"error": "Invalid credentials"}, status=status.HTTP_401_UNAUTHORIZED)

        refresh = RefreshToken.for_user(user)
        return Response({
            "user": UserSerializer(user).data,
            "tokens": {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
        }, status=status.HTTP_200_OK)

class RegisterView(generics.CreateAPIView):
    permission_classes = [IsAdminRole]
    serializer_class = UserCreateSerializer

    def _unique_username_on_default(self, base):
        base = (base or "").strip() or "user"
        u = base
        i = 1
        while User.objects.using(DEFAULT_DB).filter(username=u).exists():
            i += 1
            u = f"{base}_{i}"
        return u
    
    def create(self, request, *args, **kwargs):
        # Tell the serializer we're allowed to link by an existing email
        s = self.get_serializer(data=request.data,
                                context={"request": request,
                                         "allow_existing_email": True})
        s.is_valid(raise_exception=True)

        data     = s.validated_data
        email    = (data.get("email") or "").strip().lower()
        username = (data.get("username") or "").strip()
        password = (data.get("password") or "").strip()
        first    = (data.get("first_name") or "").strip()
        last     = (data.get("last_name") or "").strip()
        role     = data.get("role_name") or "Tutor"

        alias = get_active_semester_alias(request)

        # --- Try to locate the EOI tutor in the current semester DB by email ---
        existing_alias_user = None
        if alias and alias != DEFAULT_DB and email:
            _ensure_alias_username_column(alias)
            existing_alias_user = User.objects.using(alias).filter(email__iexact=email).first()

        # --- Ensure a platform account on DEFAULT (that’s the account that logs in) ---
        # If a platform user exists, update it; otherwise create it.
        platform_user = User.objects.using(DEFAULT_DB).filter(email__iexact=email).first() if email else None
        # Choose a username (unique on DEFAULT)
        if platform_user:
            if username and platform_user.username != username:
                # If requested username clashes with someone else, uniquify it
                if User.objects.using(DEFAULT_DB).filter(username=username).exclude(id=platform_user.id).exists():
                    username = self._unique_username_on_default(username)
                platform_user.username = username or platform_user.username
            # Update details/password
            if first: platform_user.first_name = first
            if last:  platform_user.last_name  = last
            if password: platform_user.set_password(password)
            platform_user.is_active = True
            platform_user.save(using=DEFAULT_DB)
            # Assign/refresh role on default
            platform_user.assign_role(role)
            info_msg = "Linked to existing platform account"
        else:
            # No platform user yet → create one on DEFAULT with a unique username
            if not username:
                username = (email.split("@", 1)[0] if email else None) or "user"
            username = self._unique_username_on_default(username)
            platform_user = User.objects.create_user(
                username=username,
                password=password,
                role_name=role,
                email=email,
                first_name=first,
                last_name=last,
                is_active=True,
            )
            info_msg = "Created platform account and linked to EOI"

        # --- (Optional) also stamp a username into the alias user for consistency ---
        if existing_alias_user and not existing_alias_user.username:
            # Keep usernames readable but avoid collisions inside alias
            base = platform_user.username
            u = base
            i = 1
            while User.objects.using(alias).filter(username=u).exists():
                i += 1
                u = f"{base}_{i}"
            existing_alias_user.username = u
            # No need to set password on alias; login uses DEFAULT
            if first: existing_alias_user.first_name = first
            if last:  existing_alias_user.last_name  = last
            existing_alias_user.is_active = True
            existing_alias_user.save(using=alias)

        # Build tokens for immediate login if you want
        try:
            refresh = RefreshToken.for_user(platform_user)
            tokens = {"access": str(refresh.access_token), "refresh": str(refresh)}
        except Exception:
            tokens = None

        return Response(
            {"user": UserSerializer(platform_user).data,
             "tokens": tokens,
             "info": info_msg},
            status=status.HTTP_200_OK,
        )
    
class UserUpdatePermission(BasePermission):
    """Custom permission for user updates - Admin/Coordinator can update any user, users can update themselves."""
    
    def has_permission(self, request, view):
        """Check basic authentication."""
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        """Check if user can update the target user."""
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Admin and staff can update anyone
        if request.user.is_staff or request.user.has_role('Admin'):
            return True
        
        # Coordinators can update anyone
        if request.user.has_role('Coordinator'):
            return True
        
        # Users can update themselves
        if isinstance(obj, User) and obj == request.user:
            return True
        
        return False


class UserUpdateView(APIView):
    """Update user information."""
    permission_classes = [UserUpdatePermission]
    
    @extend_schema(
        request=UserUpdateSerializer,
        responses={200: UserUpdateSerializer},
        description="Update user information",
        operation_id="user_update", 
        examples=[
            OpenApiExample(
                'User Update Example',
                value={
                    'first_name': 'Jane',
                    'last_name': 'Smith'
                },
                request_only=True,
            ),
        ]
    )
    def put(self, request, user_id=None):
        """Update a user (self; or Admin/Coordinator can update others)."""
        if user_id is not None:
            try:
                user = User.objects.using(DEFAULT_DB).get(id=user_id)
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
            # Enforce object-level permission policy
            self.check_object_permissions(request, user)
            # Only Admin/staff can set 'note'
            if 'note' in (request.data or {}) and not (
                request.user.is_staff or request.user.has_role('Admin')
            ):
                return Response({'error': 'Only Admin can set notes'}, status=status.HTTP_403_FORBIDDEN)
        else:
            user = request.user
        
        serializer = UserUpdateSerializer(user, data=request.data, partial=True)
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RoleListCreateView(generics.ListCreateAPIView):
    """List all roles or create new ones."""
    queryset = Role.objects.using(DEFAULT_DB).all()
    serializer_class = RoleSerializer
    permission_classes = [IsAdminRole]
    
    @extend_schema(
        request=RoleSerializer,
        responses={201: RoleSerializer},
        description="Create a new role",
        examples=[
            OpenApiExample(
                'Role Creation Example',
                value={
                    'role_name': 'TestRole',
                    'description': 'A test role for demonstration'
                },
                request_only=True,
            ),
        ]
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class RoleDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific role."""
    queryset = Role.objects.using(DEFAULT_DB).all()
    serializer_class = RoleSerializer
    permission_classes = [IsAdminRole]
    
    @extend_schema(
        responses={200: RoleSerializer},
        description="Retrieve a specific role"
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        request=RoleSerializer,
        responses={200: RoleSerializer},
        description="Update a specific role"
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)
    
    @extend_schema(
        responses={204: None},
        description="Delete a specific role"
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)

class UserSearchView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        q = (request.query_params.get("q") or "").strip()
        if not q:
            return Response([], status=200)

        qs = User.objects.using(DEFAULT_DB).all()
        if "@" in q:
            qs = qs.filter(email__icontains=q)
        else:
            qs = qs.filter(
                Q(username__icontains=q) |
                Q(first_name__icontains=q) |
                Q(last_name__icontains=q)
            )
        data = [{
            "id": u.id,
            "name": u.get_full_name() or u.username,
            "username": u.username,
            "email": u.email,
        } for u in qs.order_by("username")[:10]]
        return Response(data, status=200)

class PermissionListCreateView(generics.ListCreateAPIView):
    """List all permissions or create new ones."""
    queryset = Permission.objects.using(DEFAULT_DB).all()
    serializer_class = PermissionSerializer
    permission_classes = [IsAdminRole]
    
    @extend_schema(
        request=PermissionSerializer,
        responses={201: PermissionSerializer},
        description="Create a new permission",
        examples=[
            OpenApiExample(
                'Permission Creation Example',
                value={
                    'permission_key': 'create_user',
                    'description': 'Permission to create new users'
                },
                request_only=True,
            ),
        ]
    )
    def post(self, request, *args, **kwargs):
        return super().post(request, *args, **kwargs)


class PermissionDetailView(generics.RetrieveUpdateDestroyAPIView):
    """Retrieve, update, or delete a specific permission."""
    queryset = Permission.objects.using(DEFAULT_DB).all()
    serializer_class = PermissionSerializer
    permission_classes = [IsAdminRole]
    
    @extend_schema(
        responses={200: PermissionSerializer},
        description="Retrieve a specific permission"
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
    
    @extend_schema(
        request=PermissionSerializer,
        responses={200: PermissionSerializer},
        description="Update a specific permission"
    )
    def put(self, request, *args, **kwargs):
        return super().put(request, *args, **kwargs)
    
    @extend_schema(
        responses={204: None},
        description="Delete a specific permission"
    )
    def delete(self, request, *args, **kwargs):
        return super().delete(request, *args, **kwargs)


class UserRoleAssignSerializer(serializers.Serializer):
    """Serializer for user role assignment request."""
    user_id = serializers.IntegerField(help_text="ID of the user to assign role to")
    role_id = serializers.IntegerField(help_text="ID of the role to assign")


class UserRoleUpdateSerializer(serializers.Serializer):
    """Serializer for user role update request."""
    role_id = serializers.IntegerField(help_text="ID of the role to assign to the user")
    
    
class UserRolesByNameSerializer(serializers.Serializer):
    """Serializer for user role assignment by role name."""
    role_name = serializers.CharField(help_text="Name of the role to assign")


class UserRolesListView(APIView):
    """List all user-role assignments or assign roles generally."""
    permission_classes = [IsAdminRole]
    
    @extend_schema(
        responses={200: UserRolesSerializer(many=True)},
        description="Get all user-role assignments",
        operation_id="user_roles_list_all"
    )
    def get(self, request):
        """Get all active user-role assignments."""
        roles = UserRoles.objects.using(DEFAULT_DB).filter(is_active=True)
        serializer = UserRolesSerializer(roles, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    @extend_schema(
        request=UserRoleAssignSerializer,
        responses={201: UserRolesSerializer},
        description="Assign a role to a user using user_id and role_id",
        operation_id="user_roles_assign_general",
        examples=[
            OpenApiExample(
                'Role Assignment Example',
                value={
                    'user_id': 1,
                    'role_id': 2
                },
                request_only=True,
            ),
        ]
    )
    def post(self, request):
        """Assign a role to a user using user_id and role_id."""
        return self._single_assign_role(request.data)
    
    def _single_assign_role(self, data):
        """Assign a role to a single user (single active role system) - always create new instances."""
        user_id = data.get('user_id')
        role_id = data.get('role_id')
        
        if not user_id or not role_id:
            return Response(
                {'error': 'user_id and role_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.using(DEFAULT_DB).get(id=user_id)
            role = Role.objects.using(DEFAULT_DB).get(id=role_id)

            with transaction.atomic():
                # Disable ALL current active roles for this user (single active role system)
                current_assignments = UserRoles.objects.using(DEFAULT_DB).filter(user=user, is_active=True)
                disabled_roles = []
                
                for assignment in current_assignments:
                    assignment.disable()
                    disabled_roles.append(assignment.role.role_name)
                
                if disabled_roles:
                    console.print(f"[yellow] Disabled previous roles for {user.username}: {', '.join(disabled_roles)}[/yellow]")
                
                # ALWAYS create a new UserRole instance for proper auditing trail
                user_role = UserRoles.objects.using(DEFAULT_DB).create(
                    user=user, role=role, is_active=True
                )
                console.print(f"[green] Created new role assignment {role.role_name} for user {user.username}[/green]")
            
            serializer = UserRolesSerializer(user_role)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        except (User.DoesNotExist, Role.DoesNotExist) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )


class UserRolesView(APIView):
    """Manage roles for a specific user."""
    permission_classes = [IsAdminRole]
    
    @extend_schema(
        responses={200: UserRolesSerializer(many=True)},
        description="Get roles for a specific user",
        operation_id="user_roles_list_by_user"
    )
    def get(self, request, user_id):
        """Get roles for a specific user."""
        try:
            user = User.objects.using(DEFAULT_DB).get(id=user_id)
            roles = UserRoles.objects.using(DEFAULT_DB).filter(user=user, is_active=True)
            serializer = UserRolesSerializer(roles, many=True)
            return Response({
                'user': UserSerializer(user).data,
                'roles': serializer.data
            }, status=status.HTTP_200_OK)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

    def post(self, request, user_id):
        """Assign a role to a specific user using role name."""
        role_name = request.data.get('role_name')
        if not role_name:
            return Response({'error': 'role_name is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            role = Role.objects.using(DEFAULT_DB).get(role_name=role_name)
            data = {'user_id': user_id, 'role_id': role.id}
            return self._single_assign_role(data)
        except Role.DoesNotExist:
            return Response({'error': f'Role {role_name} not found'}, status=status.HTTP_404_NOT_FOUND)

    def _single_assign_role(self, data):
        """Assign a role to a single user (single active role system) - always create new instances."""
        user_id = data.get('user_id')
        role_id = data.get('role_id')
        
        try:
            user = User.objects.using(DEFAULT_DB).get(id=user_id)
            role = Role.objects.using(DEFAULT_DB).get(id=role_id)
            
            with transaction.atomic():
                # Disable ALL current active roles for this user (single active role system)
                current_assignments = UserRoles.objects.using(DEFAULT_DB).filter(user=user, is_active=True)
                disabled_roles = []
                
                for assignment in current_assignments:
                    assignment.disable()
                    disabled_roles.append(assignment.role.role_name)
                
                if disabled_roles:
                    console.print(f"[yellow]• Disabled previous roles for {user.username}: {', '.join(disabled_roles)}[/yellow]")
                
                # ALWAYS create a new UserRole instance for proper auditing trail
                user_role = UserRoles.objects.using(DEFAULT_DB).create(
                    user=user, role=role, is_active=True
                )
                console.print(f"[green]✓ Created new role assignment {role.role_name} for user {user.username}[/green]")
            
            serializer = UserRolesSerializer(user_role)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        
        except (User.DoesNotExist, Role.DoesNotExist) as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @extend_schema(
        request=UserRoleUpdateSerializer,
        responses={200: UserRolesSerializer},
        description="Update the role for a specific user",
        operation_id="user_roles_update_for_user",
        examples=[
            OpenApiExample(
                'Role Update Example',
                value={
                    'role_id': 1
                },
                request_only=True,
            ),
        ]
    )
    def put(self, request, user_id):
        """Update the role for a specific user (single active role system) - always create new instances."""
        try:
            user = User.objects.using(DEFAULT_DB).get(id=user_id)
            role_id = request.data.get('role_id')
            
            if not role_id:
                return Response(
                    {'error': 'role_id is required'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                role = Role.objects.using(DEFAULT_DB).get(id=role_id)
            except Role.DoesNotExist:
                return Response(
                    {'error': f'Role with id {role_id} does not exist'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            with transaction.atomic():
                # Disable ALL current active roles for this user (single active role system)
                current_assignments = UserRoles.objects.using(DEFAULT_DB).filter(user=user, is_active=True)
                disabled_roles = []
                
                for assignment in current_assignments:
                    assignment.disable()
                    disabled_roles.append(assignment.role.role_name)
                
                if disabled_roles:
                    console.print(f"[yellow]• Disabled previous roles for {user.username}: {', '.join(disabled_roles)}[/yellow]")
                
                # ALWAYS create a new UserRole instance for proper auditing trail
                user_role = UserRoles.objects.using(DEFAULT_DB).create(
                    user=user, role=role, is_active=True
                )
                console.print(f"[green]✓ Created new role assignment {role.role_name} for user {user.username}[/green]")
                
                serializer = UserRolesSerializer(user_role)
                return Response(serializer.data, status=status.HTTP_200_OK)
        
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    def delete(self, request, user_id):
        try:
            user = User.objects.using(DEFAULT_DB).get(id=user_id)
            
            with transaction.atomic():
                # Get current active roles
                current_assignments = UserRoles.objects.using(DEFAULT_DB).filter(user=user, is_active=True)

                if not current_assignments.exists():
                    return Response(
                        {'error': 'User has no active roles to remove'},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                # Disable all current active roles (for auditing)
                disabled_roles = []
                for assignment in current_assignments:
                    assignment.disable()
                    disabled_roles.append(assignment.role.role_name)
                
                console.print(f"[yellow] Disabled roles for {user.email}: {', '.join(disabled_roles)}[/yellow]")
                return Response(status=status.HTTP_204_NO_CONTENT)                

        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

class UserProfileView(APIView):
    """Get user profile with roles and permissions."""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        responses={200: dict},
        description="Get user profile with roles, permissions, and supervisor details",
        operation_id="user_profile"  # static id is fine
    )
    def get(self, request, user_id=None):
        # Load target user
        if user_id is not None:
            # Only self or staff/admin can fetch arbitrary user ids
            if not (request.user.is_staff or request.user.id == user_id or request.user.has_role('Admin')):
                return Response({'error': 'Permission denied'}, status=status.HTTP_403_FORBIDDEN)
            try:
                user = User.objects.using(DEFAULT_DB).get(id=user_id)
            except User.DoesNotExist:
                return Response({'error': 'User not found'}, status=status.HTTP_404_NOT_FOUND)
        else:
            user = request.user  # already authenticated

        # Roles & permissions (these methods are already default-DB aware)
        roles = user.get_user_roles()
        permissions = user.get_user_permissions()

        # Supervisor details
        is_supervisor = hasattr(user, 'supervisor')
        supervisor_data = SupervisorSerializer(user.supervisor).data if is_supervisor else None

        # Build user payload and hide 'note' unless self or admin/staff
        user_payload = UserSerializer(user).data
        if not (request.user.is_staff or request.user.has_role('Admin') or request.user.id == user.id):
            user_payload.pop('note', None)

        return Response({
            'user': user_payload,
            'roles': [{'id': r.id, 'name': r.role_name} for r in roles],
            'permissions': [{'id': p.id, 'key': p.permission_key} for p in permissions],
            'is_supervisor': is_supervisor,
            'supervisor_details': supervisor_data,
        }, status=status.HTTP_200_OK)

# Add password reset functionality
class PasswordResetSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    new_password = serializers.CharField(min_length=8)

# Add a view
class ResetPasswordView(APIView):
    permission_classes = [IsAdminRole]

    @extend_schema(
        request=PasswordResetSerializer,
        responses={200: dict},
        description="Admin-only: reset another user's password"
    )
    def post(self, request):
        s = PasswordResetSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user_id = s.validated_data["user_id"]
        new_password = s.validated_data["new_password"]

        try:
            user = User.objects.using(DEFAULT_DB).get(id=user_id)
        except User.DoesNotExist:
            return Response({"error": "User not found"}, status=404)

        user.set_password(new_password)
        user.save(using=DEFAULT_DB, update_fields=["password"])
        return Response({"ok": True}, status=200)