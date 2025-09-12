"""
Test URLs for the users app.
"""
from django.test import TestCase
from django.urls import reverse, resolve
from users import views


class URLTestCase(TestCase):
    """Test cases for URL patterns."""
    
    def test_login_url(self):
        """Test login URL pattern."""
        url = reverse('accounts:login')
        self.assertEqual(url, '/api/users/login/')
        resolver = resolve(url)
        self.assertEqual(resolver.func.view_class, views.LoginView)
    
    def test_register_url(self):
        """Test register URL pattern."""
        url = reverse('accounts:register')
        self.assertEqual(url, '/api/users/register/')
        resolver = resolve(url)
        self.assertEqual(resolver.func.view_class, views.RegisterView)
    
    def test_profile_url(self):
        """Test profile URL pattern."""
        url = reverse('accounts:profile')
        self.assertEqual(url, '/api/users/profile/')
        resolver = resolve(url)
        self.assertEqual(resolver.func.view_class, views.UserProfileView)
    
    def test_user_profile_url(self):
        """Test user profile with ID URL pattern."""
        url = reverse('accounts:user_profile', kwargs={'user_id': 1})
        self.assertEqual(url, '/api/users/profile/1/')
        resolver = resolve(url)
        self.assertEqual(resolver.func.view_class, views.UserProfileView)
    
    def test_user_update_self_url(self):
        """Test user self-update URL pattern."""
        url = reverse('accounts:user_update_self')
        self.assertEqual(url, '/api/users/users/update/')
        resolver = resolve(url)
        self.assertEqual(resolver.func.view_class, views.UserUpdateView)
    
    def test_user_update_url(self):
        """Test user update with ID URL pattern."""
        url = reverse('accounts:user_update', kwargs={'user_id': 1})
        self.assertEqual(url, '/api/users/users/update/1/')
        resolver = resolve(url)
        self.assertEqual(resolver.func.view_class, views.UserUpdateView)
    
    def test_bulk_user_update_url(self):
        """Test bulk user update URL pattern."""
        url = reverse('accounts:bulk_user_update')
        self.assertEqual(url, '/api/users/users/bulk-update/')
        resolver = resolve(url)
        self.assertEqual(resolver.func.view_class, views.UserUpdateView)
    
    def test_roles_list_create_url(self):
        """Test roles list/create URL pattern."""
        url = reverse('accounts:roles_list_create')
        self.assertEqual(url, '/api/users/roles/')
        resolver = resolve(url)
        self.assertEqual(resolver.func.view_class, views.RoleListCreateView)
    
    def test_role_detail_url(self):
        """Test role detail URL pattern."""
        url = reverse('accounts:role_detail', kwargs={'pk': 1})
        self.assertEqual(url, '/api/users/roles/1/')
        resolver = resolve(url)
        self.assertEqual(resolver.func.view_class, views.RoleDetailView)
    
    def test_permissions_list_create_url(self):
        """Test permissions list/create URL pattern."""
        url = reverse('accounts:permissions_list_create')
        self.assertEqual(url, '/api/users/permissions/')
        resolver = resolve(url)
        self.assertEqual(resolver.func.view_class, views.PermissionListCreateView)
    
    def test_permission_detail_url(self):
        """Test permission detail URL pattern."""
        url = reverse('accounts:permission_detail', kwargs={'pk': 1})
        self.assertEqual(url, '/api/users/permissions/1/')
        resolver = resolve(url)
        self.assertEqual(resolver.func.view_class, views.PermissionDetailView)
    
    def test_user_roles_list_url(self):
        """Test user roles list URL pattern."""
        url = reverse('accounts:user_roles_list')
        self.assertEqual(url, '/api/users/user-roles/')
        resolver = resolve(url)
        self.assertEqual(resolver.func.view_class, views.UserRolesView)
    
    def test_user_roles_detail_url(self):
        """Test user roles detail URL pattern."""
        url = reverse('accounts:user_roles_detail', kwargs={'user_id': 1})
        self.assertEqual(url, '/api/users/user-roles/1/')
        resolver = resolve(url)
        self.assertEqual(resolver.func.view_class, views.UserRolesView)
    
    def test_user_roles_assign_url(self):
        """Test user roles assign URL pattern."""
        url = reverse('accounts:user_roles_assign', kwargs={'user_id': 1})
        self.assertEqual(url, '/api/users/user-roles/1/assign/')
        resolver = resolve(url)
        self.assertEqual(resolver.func.view_class, views.UserRolesView)
    
    def test_user_roles_update_url(self):
        """Test user roles update URL pattern."""
        url = reverse('accounts:user_roles_update', kwargs={'user_id': 1})
        self.assertEqual(url, '/api/users/user-roles/1/update/')
        resolver = resolve(url)
        self.assertEqual(resolver.func.view_class, views.UserRolesView)
    
    def test_user_role_disable_url(self):
        """Test user role disable URL pattern."""
        url = reverse('accounts:user_role_disable', kwargs={'user_id': 1, 'role_id': 2})
        self.assertEqual(url, '/api/users/user-roles/1/role/2/disable/')
        resolver = resolve(url)
        self.assertEqual(resolver.func.view_class, views.UserRolesView)
    
    def test_token_obtain_pair_url(self):
        """Test JWT token obtain pair URL pattern."""
        url = reverse('accounts:token_obtain_pair')
        self.assertEqual(url, '/api/users/token/')
    
    def test_token_refresh_url(self):
        """Test JWT token refresh URL pattern."""
        url = reverse('accounts:token_refresh')
        self.assertEqual(url, '/api/users/token/refresh/')
