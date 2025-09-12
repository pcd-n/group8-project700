from django.contrib import admin
from .models import User, Role, Permission, RolePermission, UserRoles, Campus, Supervisor


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """Custom admin for User model."""
    list_display = ['email', 'first_name', 'last_name', 'is_active', 'is_staff', 'created_at', 'get_roles']
    list_filter = ['is_active', 'is_staff', 'created_at']
    search_fields = ['email', 'first_name', 'last_name']
    ordering = ['email']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Authentication', {
            'fields': ('email', 'password')
        }),
        ('Personal Information', {
            'fields': ('first_name', 'last_name')
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff'),
        }),
        ('Important Dates', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = (
        ('Create User', {
            'classes': ('wide',),
            'fields': ('email', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )
    
    def get_roles(self, obj):
        """Display user roles."""
        roles = obj.user_roles.all()
        if roles:
            role_names = [role.role.role_name for role in roles]
            return ', '.join(role_names)
        return 'No roles assigned'
    get_roles.short_description = 'Roles'


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    """Admin for Role model."""
    list_display = ['role_name', 'description', 'get_permissions_count', 'get_users_count', 'created_at']
    search_fields = ['role_name', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['role_name']
    
    def get_permissions_count(self, obj):
        """Count of permissions for this role."""
        return obj.role_permissions.count()
    get_permissions_count.short_description = 'Permissions'
    
    def get_users_count(self, obj):
        """Count of users with this role."""
        return obj.user_roles.count()
    get_users_count.short_description = 'Users'


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    """Admin for Permission model."""
    list_display = ['permission_key', 'description', 'get_roles_count', 'created_at']
    search_fields = ['permission_key', 'description']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['permission_key']
    
    def get_roles_count(self, obj):
        """Count of roles with this permission."""
        return obj.rolepermission_set.count()
    get_roles_count.short_description = 'Roles'


@admin.register(RolePermission)
class RolePermissionAdmin(admin.ModelAdmin):
    """Admin for RolePermission model."""
    list_display = ['role', 'permission']
    list_filter = ['role']
    search_fields = ['role__role_name', 'permission__permission_key']
    ordering = ['role__role_name', 'permission__permission_key']
    
    fieldsets = (
        ('Assignment', {
            'fields': ('role', 'permission')
        }),
    )


@admin.register(UserRoles)
class UserRolesAdmin(admin.ModelAdmin):
    """Admin for UserRoles model."""
    list_display = ['user', 'role', 'assigned_at', 'is_active']
    list_filter = ['role', 'is_active', 'assigned_at']
    search_fields = ['user__email', 'user__first_name', 'user__last_name', 'role__role_name']
    readonly_fields = ['assigned_at']
    ordering = ['-assigned_at']
    
    fieldsets = (
        ('Assignment', {
            'fields': ('user', 'role', 'is_active')
        }),
        ('Metadata', {
            'fields': ('assigned_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(Campus)
class CampusAdmin(admin.ModelAdmin):
    """Admin for Campus model."""
    list_display = ['campus_name', 'campus_location', 'get_users_count', 'created_at']
    list_filter = ['created_at']
    search_fields = ['campus_name', 'campus_location']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['campus_name']
    
    fieldsets = (
        ('Campus Information', {
            'fields': ('campus_name', 'campus_location')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_users_count(self, obj):
        """Count of supervisors in this campus."""
        return obj.supervisor_set.count()
    get_users_count.short_description = 'Supervisors'


@admin.register(Supervisor)
class SupervisorAdmin(admin.ModelAdmin):
    """Admin for Supervisor model."""
    list_display = ['user', 'campus', 'created_at']
    list_filter = ['campus', 'created_at']
    search_fields = [
        'user__email', 'user__first_name', 'user__last_name'
    ]
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Relationship', {
            'fields': ('user', 'campus')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Customize foreign key fields."""
        if db_field.name == 'user':
            kwargs["queryset"] = User.objects.filter(is_active=True).order_by('email')
        return super().formfield_for_foreignkey(db_field, request, **kwargs)