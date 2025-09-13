"""
Test admin for the users app.
"""
from django.test import TestCase
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from users.admin import UserAdmin, RoleAdmin, PermissionAdmin, UserRolesAdmin
from users.models import User, Role, Permission, UserRoles

User = get_user_model()


class MockRequest:
    """Mock request object for admin tests."""
    pass


class UserAdminTestCase(TestCase):
    """Test cases for UserAdmin."""
    
    def setUp(self):
        """Set up test data."""
        self.site = AdminSite()
        self.user_admin = UserAdmin(User, self.site)
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
    
    def test_user_admin_registration(self):
        """Test that UserAdmin is properly configured."""
        self.assertEqual(self.user_admin.model, User)
        self.assertIn('email', self.user_admin.list_display)
        self.assertIn('first_name', self.user_admin.list_display)
        self.assertIn('last_name', self.user_admin.list_display)
        self.assertIn('is_active', self.user_admin.list_display)
        self.assertIn('is_staff', self.user_admin.list_display)
    
    def test_user_admin_search_fields(self):
        """Test search fields configuration."""
        if hasattr(self.user_admin, 'search_fields'):
            self.assertIn('email', self.user_admin.search_fields)
    
    def test_user_admin_list_filter(self):
        """Test list filter configuration."""
        if hasattr(self.user_admin, 'list_filter'):
            self.assertIn('is_active', self.user_admin.list_filter)
            self.assertIn('is_staff', self.user_admin.list_filter)


class RoleAdminTestCase(TestCase):
    """Test cases for RoleAdmin."""
    
    def setUp(self):
        """Set up test data."""
        self.site = AdminSite()
        self.role_admin = RoleAdmin(Role, self.site)
        self.role = Role.objects.create(
            role_name='TestRole',
            description='Test role'
        )
    
    def test_role_admin_registration(self):
        """Test that RoleAdmin is properly configured."""
        self.assertEqual(self.role_admin.model, Role)
        if hasattr(self.role_admin, 'list_display'):
            self.assertIn('role_name', self.role_admin.list_display)


class PermissionAdminTestCase(TestCase):
    """Test cases for PermissionAdmin."""
    
    def setUp(self):
        """Set up test data."""
        self.site = AdminSite()
        self.permission_admin = PermissionAdmin(Permission, self.site)
        self.permission = Permission.objects.create(
            permission_key='test.permission',
            description='Test permission'
        )
    
    def test_permission_admin_registration(self):
        """Test that PermissionAdmin is properly configured."""
        self.assertEqual(self.permission_admin.model, Permission)
        if hasattr(self.permission_admin, 'list_display'):
            self.assertIn('permission_key', self.permission_admin.list_display)


class UserRolesAdminTestCase(TestCase):
    """Test cases for UserRolesAdmin."""
    
    def setUp(self):
        """Set up test data."""
        self.site = AdminSite()
        self.user_roles_admin = UserRolesAdmin(UserRoles, self.site)
        self.user = User.objects.create_user(email='test@example.com')
        self.role = Role.objects.create(role_name='TestRole')
        self.user_role = UserRoles.objects.create(user=self.user, role=self.role)
    
    def test_user_roles_admin_registration(self):
        """Test that UserRolesAdmin is properly configured."""
        self.assertEqual(self.user_roles_admin.model, UserRoles)
        if hasattr(self.user_roles_admin, 'list_display'):
            self.assertIn('user', self.user_roles_admin.list_display)
            self.assertIn('role', self.user_roles_admin.list_display)
