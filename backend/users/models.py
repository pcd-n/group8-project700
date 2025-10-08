# backend/users/models.py
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager
from django.db import models
from django.utils import timezone
from django.contrib.auth import authenticate
from rest_framework_simplejwt.tokens import RefreshToken
import logging
from rich.console import Console
from rich.logging import RichHandler
from django.db import transaction

DEFAULT_DB = "default"
# Configure rich logging
console = Console()
logger = logging.getLogger(__name__)

# Add Rich handler if not already configured
if not logger.handlers:
    logger.addHandler(RichHandler(console=console))
    logger.setLevel(logging.INFO)

class UserManager(BaseUserManager):
    """Custom user manager for username-based authentication with OAuth support (optional)."""

    def create_user(self, username, password=None, role_name=None, **extra_fields):
        if not username:
            raise ValueError("The username field must be set")
        
        extra_fields.setdefault('is_active', True)

        if not role_name:
            role_name = 'Member'
            console.print(f"[yellow]No role specified for user {username}, assigning default role: {role_name}[/yellow]")

        with transaction.atomic():
            user = self.model(username=username, **extra_fields)
            if password:
                user.set_password(password)
            user.save(using=DEFAULT_DB)   # <-- force default
            self._assign_role_to_user(user, role_name)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_active', True)
        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        return self.create_user(username, password, role_name='Admin', **extra_fields)

    def update_user(self, user_id, **extra_fields):
        try:
            user = self.using(DEFAULT_DB).get(pk=user_id)
            for field, value in extra_fields.items():
                setattr(user, field, value)
            user.save(using=DEFAULT_DB)
            return user
        except self.model.DoesNotExist:
            return None

    def delete_user(self, user_id):
        try:
            user = self.using(DEFAULT_DB).get(pk=user_id)
            user.delete(using=DEFAULT_DB)
            return True
        except self.model.DoesNotExist:
            return False

    def login_user(self, username, password):
        """Authenticate and return user with tokens."""
        try:
            user = authenticate(username=username, password=password)
            if user and user.is_active:
                tokens = self.get_tokens_for_user(user)
                return {'user': user, 'tokens': tokens, 'success': True}
            return {'success': False, 'message': 'Invalid credentials'}
        except Exception as e:
            console.print(f"[red]Login error:[/red] {str(e)}")
            return {'success': False, 'message': 'Login failed'}

    def register_user(self, username, password, role_name=None, **extra_fields):
        try:
            if self.using(DEFAULT_DB).filter(username=username).exists():
                return {'success': False, 'message': 'User already exists'}
            if not role_name:
                role_name = 'Member'
            user = self.create_user(username=username, password=password, role_name=role_name, **extra_fields)
            tokens = self.get_tokens_for_user(user)
            return {'user': user, 'tokens': tokens, 'success': True}
        except Exception as e:
            console.print(f"[red]Registration error:[/red] {str(e)}")
            return {'success': False, 'message': f'Registration failed: {str(e)}'}

    # If you keep OAuth helpers, switch them to username too, or generate a username from provider profile.
    def oauth_login_or_create(self, username, role_name=None, **extra_fields):
        try:
            user, created = self.using(DEFAULT_DB).get_or_create(
                username=username,
                defaults=extra_fields
            )
            if created:
                if not role_name:
                    role_name = 'Member'
                self._assign_role_to_user(user, role_name)
                user.set_unusable_password()
                user.save(using=DEFAULT_DB)
                console.print(f"[green]✓ New OAuth user created:[/green] {username} -> {role_name}")
            tokens = self.get_tokens_for_user(user)
            return {'user': user, 'tokens': tokens, 'success': True, 'created': created}
        except Exception as e:
            console.print(f"[red]OAuth login error:[/red] {str(e)}")
            return {'success': False, 'message': 'OAuth authentication failed'}

    def _assign_role_to_user(self, user, role_name):
        Role = self.model._meta.apps.get_model('users', 'Role')
        UserRoles = self.model._meta.apps.get_model('users', 'UserRoles')

        essential_roles = ['Admin', 'Coordinator', 'Tutor', 'Support', 'Member']
        try:
            try:
                role = Role.objects.using(DEFAULT_DB).get(role_name=role_name)
            except Role.DoesNotExist:
                if role_name in essential_roles:
                    role, _ = Role.objects.using(DEFAULT_DB).get_or_create(
                        role_name=role_name,
                        defaults={'description': f'{role_name} role'}
                    )
                else:
                    raise ValueError(f"Role '{role_name}' does not exist and is not an essential role")

            with transaction.atomic():
                previous_roles = UserRoles.objects.using(DEFAULT_DB).filter(user=user, is_active=True)
                for user_role in previous_roles:
                    user_role.disable()  # patched below to save on default

                UserRoles.objects.using(DEFAULT_DB).create(
                    user=user,
                    role=role,
                    is_active=True
                )
        except Exception as e:
            console.print(f"[red]✗ Error assigning role to user:[/red] {str(e)}")
            raise

class User(AbstractBaseUser):
    """
    Custom User model with username as the unique identifier.
    """
    username    = models.CharField(max_length=150, unique=True, null=False, blank=False)
    email       = models.EmailField(unique=False, null=True, blank=True)  # optional
    first_name  = models.CharField(max_length=150, blank=True)
    last_name   = models.CharField(max_length=150, blank=True)
    is_active   = models.BooleanField(default=True)
    is_staff    = models.BooleanField(default=False)
    note        = models.TextField(blank=True, null=True, default=None)
    created_at  = models.DateTimeField(default=timezone.now)
    updated_at  = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD  = 'username'
    REQUIRED_FIELDS = []

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        status = "Active" if self.is_active else "Disabled"
        return f"{self.user.username} - {self.role.role_name} ({status})"

    def save(self, *args, **kwargs):
        kwargs.setdefault("using", DEFAULT_DB)
        return super().save(*args, **kwargs)

    def get_full_name(self):
        full_name = f'{self.first_name} {self.last_name}'.strip()
        return full_name or self.username

    def get_short_name(self):
        return self.first_name or self.username
    
    # Required methods for Django admin compatibility without PermissionsMixin
    def has_perm(self, perm, obj=None):
        """
        Return True if user has the specified permission.
        You'll implement your custom permission logic here.
        """
        return self.is_staff  # For now, staff users have all permissions
    
    def has_module_perms(self, app_label):
        """
        Return True if user has permissions to view the app `app_label`.
        You'll implement your custom permission logic here.
        """
        return self.is_staff  # For now, staff users can access all apps
    
    def has_custom_permission(self, permission_key):
        """Check if user has a specific custom permission (on default DB)."""
        Apps = self._meta.apps
        Permission     = Apps.get_model('users', 'Permission')
        RolePermission = Apps.get_model('users', 'RolePermission')
        UserRoles      = Apps.get_model('users', 'UserRoles')

        return Permission.objects.using(DEFAULT_DB).filter(
            permission_key=permission_key,
            rolepermission__in=RolePermission.objects.using(DEFAULT_DB).filter(
                role__userroles__in=UserRoles.objects.using(DEFAULT_DB).filter(
                    user=self, is_active=True
                )
            )
        ).exists()
        
    def get_user_roles(self):
        """Get all active roles for this user (default DB)."""
        Apps = self._meta.apps
        Role = Apps.get_model('users', 'Role')
        return Role.objects.using(DEFAULT_DB).filter(
            userroles__user=self,
            userroles__is_active=True
        )

    def get_active_role(self):
        UserRoles = self._meta.apps.get_model('users', 'UserRoles')
        ur = (UserRoles.objects.using(DEFAULT_DB)
            .filter(user=self, is_active=True)
            .select_related('role')
            .first())
        return ur.role if ur else None
    
    def get_active_role_name(self):
        """Get the user's active role name."""
        role = self.get_active_role()
        return role.role_name if role else None
    
    def get_user_permissions(self):
        """Get all distinct permissions assigned via the user's active roles (default DB)."""
        Apps = self._meta.apps
        Permission     = Apps.get_model('users', 'Permission')
        RolePermission = Apps.get_model('users', 'RolePermission')

        return Permission.objects.using(DEFAULT_DB).filter(
            rolepermission__in=RolePermission.objects.using(DEFAULT_DB).filter(
                role__userroles__user=self,
                role__userroles__is_active=True
            )
        ).distinct()
        
    def assign_role(self, role_name):
        """Assign a role to this user (single active role only)."""
        # Use the manager method which handles single active role logic
        User.objects._assign_role_to_user(self, role_name)
    
    def remove_role(self, role_name):
        """
        Disable the specified active role for this user on default DB.
        If no active roles remain, assign 'Member' as a fallback (creating it if needed).
        """
        Apps = self._meta.apps
        Role      = Apps.get_model('users', 'Role')
        UserRoles = Apps.get_model('users', 'UserRoles')

        try:
            with transaction.atomic():
                role = Role.objects.using(DEFAULT_DB).get(role_name=role_name)
                user_role = UserRoles.objects.using(DEFAULT_DB).get(user=self, role=role, is_active=True)
                # Disable current role (UserRoles.disable() must save using DEFAULT_DB)
                user_role.disable()

                # If no roles remain active, fallback to Member
                remaining = UserRoles.objects.using(DEFAULT_DB).filter(user=self, is_active=True)
                if not remaining.exists():
                    member_role, _ = Role.objects.using(DEFAULT_DB).get_or_create(
                        role_name='Member',
                        defaults={'description': 'Member role'}
                    )
                    UserRoles.objects.using(DEFAULT_DB).create(
                        user=self,
                        role=member_role,
                        is_active=True
                    )
            return True

        except (Role.DoesNotExist, UserRoles.DoesNotExist):
            # Role not found or not active for this user
            return False
    
    def has_role(self, role_name):
        """True if user has the given active role (default DB)."""
        Apps = self._meta.apps
        UserRoles = Apps.get_model('users', 'UserRoles')
        return UserRoles.objects.using(DEFAULT_DB).filter(
            user=self,
            role__role_name=role_name,
            is_active=True
        ).exists()
    
    def get_primary_role(self):
        """Get the user's active role (same as get_active_role since single role system)."""
        return self.get_active_role()

class Role(models.Model):
    """Role model for custom permission system."""
    role_name = models.CharField(max_length=100, unique=True, null=False)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'
    
    def __str__(self):
        return self.role_name


class Permission(models.Model):
    """Permission model for custom permission system."""
    permission_key = models.CharField(max_length=200, unique=True, null=False)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Permission'
        verbose_name_plural = 'Permissions'
    
    def __str__(self):
        return self.permission_key


class RolePermission(models.Model):
    """Many-to-many relationship between roles and permissions."""
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ('role', 'permission')
        verbose_name = 'Role Permission'
        verbose_name_plural = 'Role Permissions'
    
    def __str__(self):
        return f"{self.role.role_name} - {self.permission.permission_key}"


class UserRoles(models.Model):
    """Many-to-many relationship between users and roles with auditing support."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)
    assigned_at = models.DateTimeField(default=timezone.now)
    is_active = models.BooleanField(default=True)  # For auditing purposes
    disabled_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'User Role'
        verbose_name_plural = 'User Roles'
        # Remove unique_together to allow multiple records for auditing
    
    def __str__(self):
        status = "Active" if self.is_active else "Disabled"
        return f"{self.user.email} - {self.role.role_name} ({status})"
    
    def disable(self):
        self.is_active = False
        self.disabled_at = timezone.now()
        self.save(using=DEFAULT_DB)


# Campus Enum Choices
class CampusName(models.TextChoices):
    SB = 'SB', 'Hobart'
    IR = 'IR', 'Launceston'
    ONLINE = 'ONLINE', 'Online'


class Campus(models.Model):
    """Campus model."""
    campus_name = models.CharField(
        max_length=20,
        choices=CampusName.choices,
        unique=True,
        null=False
    )
    campus_location = models.CharField(max_length=255, null=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Campus'
        verbose_name_plural = 'Campuses'
    
    def __str__(self):
        return f"{self.campus_name} - {self.campus_location}"


class Supervisor(models.Model):
    """Supervisor model - specific users who supervise tutors."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, unique=True)
    campus = models.ForeignKey(Campus, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Supervisor'
        verbose_name_plural = 'Supervisors'
    
def __str__(self):
    name = self.user.get_full_name() or self.user.username
    return f"Supervisor: {name}"

