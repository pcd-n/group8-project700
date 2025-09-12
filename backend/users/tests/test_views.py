"""
Test views for the users app.
"""
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from unittest.mock import patch, MagicMock
from users.models import User, Role, Permission, UserRoles, Campus, CampusName, Supervisor

User = get_user_model()


class ViewTestHelpers:
    """Helper methods for setting up test data with proper roles."""
    
    @staticmethod
    def create_test_roles():
        """Create the actual roles used in the system."""
        roles = {}
        roles['admin'] = Role.objects.get_or_create(
            role_name='Admin', 
            defaults={'description': 'Administrator with full system access'}
        )[0]
        roles['coordinator'] = Role.objects.get_or_create(
            role_name='Coordinator', 
            defaults={'description': 'Coordinator with management privileges'}
        )[0]
        roles['tutor'] = Role.objects.get_or_create(
            role_name='Tutor', 
            defaults={'description': 'Tutor role'}
        )[0]
        roles['support'] = Role.objects.get_or_create(
            role_name='Support', 
            defaults={'description': 'Support staff role'}
        )[0]
        roles['member'] = Role.objects.get_or_create(
            role_name='Member', 
            defaults={'description': 'Default member role'}
        )[0]
        return roles
    
    @staticmethod
    def create_user_with_role(email, role_name, password='testpass123'):
        """Create a user and assign them a specific role."""
        # Create user with staff status for admin users
        is_staff = role_name.lower() == 'admin'
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name='Test',
            last_name='User',
            is_staff=is_staff
        )
        roles = ViewTestHelpers.create_test_roles()
        if role_name.lower() in roles:
            UserRoles.objects.create(
                user=user,
                role=roles[role_name.lower()],
                is_active=True
            )
        return user


class LoginViewTestCase(APITestCase):
    """Test cases for LoginView."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        self.url = reverse('accounts:login')
    
    def test_successful_login(self):
        """Test successful login."""
        data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('user', response.data)
        self.assertIn('tokens', response.data)
        self.assertEqual(response.data['user']['email'], 'test@example.com')
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        data = {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        }
        
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)


class RegisterViewTestCase(APITestCase):
    """Test cases for RegisterView."""
    
    def setUp(self):
        """Set up test data."""
        self.url = reverse('accounts:register')
        self.campus = Campus.objects.create(
            campus_name=CampusName.SB,
            campus_location='Hobart'
        )
        # Create actual system roles
        self.roles = ViewTestHelpers.create_test_roles()
    
    def test_successful_registration(self):
        """Test successful user registration."""
        data = {
            'email': 'newuser@example.com',
            'password': 'newpass123',
            'first_name': 'New',
            'last_name': 'User'
        }
        
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('user', response.data)
        self.assertIn('tokens', response.data)
        self.assertEqual(response.data['user']['email'], 'newuser@example.com')
        self.assertFalse(response.data['is_supervisor'])
    
    def test_registration_with_roles(self):
        """Test registration with role assignment."""
        data = {
            'email': 'newuser@example.com',
            'password': 'newpass123',
            'first_name': 'New',
            'last_name': 'User',
            'roles': ['Tutor']  # Use actual role name
        }
        
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email='newuser@example.com')
        self.assertTrue(user.has_role('Tutor'))


class UserUpdateViewTestCase(APITestCase):
    """Test cases for UserUpdateView with proper permission testing."""
    
    def setUp(self):
        """Set up test data."""
        self.roles = ViewTestHelpers.create_test_roles()
        self.admin_user = ViewTestHelpers.create_user_with_role('admin@example.com', 'Admin')
        self.coordinator_user = ViewTestHelpers.create_user_with_role('coordinator@example.com', 'Coordinator')
        self.regular_user = ViewTestHelpers.create_user_with_role('user@example.com', 'Member')
        self.target_user = ViewTestHelpers.create_user_with_role('target@example.com', 'Tutor')
    
    def test_user_update_own_profile(self):
        """Test user updating their own profile."""
        self.client.force_authenticate(user=self.regular_user)
        url = reverse('accounts:user_update_self')
        
        data = {
            'first_name': 'Updated',
            'last_name': 'Name'
        }
        
        response = self.client.put(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.regular_user.refresh_from_db()
        self.assertEqual(self.regular_user.first_name, 'Updated')
        self.assertEqual(self.regular_user.last_name, 'Name')
    
    def test_admin_update_other_user(self):
        """Test admin user updating another user."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('accounts:user_update_specific', kwargs={'user_id': self.target_user.id})
        
        data = {
            'first_name': 'AdminUpdated',
            'is_active': True
        }
        
        response = self.client.put(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.target_user.refresh_from_db()
        self.assertEqual(self.target_user.first_name, 'AdminUpdated')


class RoleListCreateViewTestCase(APITestCase):
    """Test cases for RoleListCreateView with proper permission testing."""
    
    def setUp(self):
        """Set up test data."""
        self.roles = ViewTestHelpers.create_test_roles()
        self.admin_user = ViewTestHelpers.create_user_with_role('admin@example.com', 'Admin')
        self.regular_user = ViewTestHelpers.create_user_with_role('user@example.com', 'Member')
        self.url = reverse('accounts:roles_list_create')
    
    def test_list_roles_as_admin(self):
        """Test listing all roles as admin user."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Handle both list and paginated responses
        data = response.data
        if isinstance(data, dict) and 'results' in data:
            data = data['results']
        
        # Check that all actual roles exist
        role_names = [r['role_name'] for r in data]
        expected_roles = ['Admin', 'Coordinator', 'Tutor', 'Support', 'Member']
        for role in expected_roles:
            self.assertIn(role, role_names)
    
    def test_create_role_as_admin(self):
        """Test creating a new role as admin user."""
        self.client.force_authenticate(user=self.admin_user)
        data = {
            'role_name': 'NewTestRole',
            'description': 'A new test role'
        }
        
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['role_name'], 'NewTestRole')
        self.assertTrue(Role.objects.filter(role_name='NewTestRole').exists())


class PermissionListCreateViewTestCase(APITestCase):
    """Test cases for PermissionListCreateView."""
    
    def setUp(self):
        """Set up test data."""
        self.roles = ViewTestHelpers.create_test_roles()
        self.admin_user = ViewTestHelpers.create_user_with_role('admin@example.com', 'Admin')
        self.permission = Permission.objects.create(permission_key='existing.permission')
        self.url = reverse('accounts:permissions_list_create')
        self.client = APIClient()
        self.client.force_authenticate(user=self.admin_user)
    
    def test_list_permissions(self):
        """Test listing all permissions."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Handle both list and paginated responses
        data = response.data
        if isinstance(data, dict) and 'results' in data:
            data = data['results']
        # Check that our test permission exists
        permission_keys = [p['permission_key'] for p in data]
        self.assertIn('existing.permission', permission_keys)
    
    def test_create_permission(self):
        """Test creating a new permission."""
        data = {
            'permission_key': 'new.permission',
            'description': 'A new permission'
        }
        
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['permission_key'], 'new.permission')
        self.assertTrue(Permission.objects.filter(permission_key='new.permission').exists())


class UserRolesViewTestCase(APITestCase):
    """Test cases for UserRolesView with proper permission testing."""
    
    def setUp(self):
        """Set up test data."""
        self.roles = ViewTestHelpers.create_test_roles()
        self.admin_user = ViewTestHelpers.create_user_with_role('admin@example.com', 'Admin')
        self.coordinator_user = ViewTestHelpers.create_user_with_role('coordinator@example.com', 'Coordinator')
        self.regular_user = ViewTestHelpers.create_user_with_role('user@example.com', 'Member')
        self.target_user = ViewTestHelpers.create_user_with_role('target@example.com', 'Tutor')
    
    def test_list_user_roles_as_admin(self):
        """Test listing all user roles as admin."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('accounts:user_roles_list')
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should return list of user role assignments
        self.assertIsInstance(response.data, list)
    
    def test_get_specific_user_roles_as_admin(self):
        """Test getting roles for a specific user as admin."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('accounts:user_roles_manage', kwargs={'user_id': self.target_user.id})
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should show the user's current roles
        self.assertIn('roles', response.data)
    
    def test_assign_role_as_admin(self):
        """Test assigning role to user as admin."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('accounts:user_roles_manage', kwargs={'user_id': self.regular_user.id})
        data = {
            'role_name': 'Support'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Check that role was assigned
        self.assertTrue(self.regular_user.has_role('Support'))


class UserProfileViewTestCase(APITestCase):
    """Test cases for UserProfileView."""
    
    def setUp(self):
        """Set up test data."""
        self.roles = ViewTestHelpers.create_test_roles()
        self.user = ViewTestHelpers.create_user_with_role('test@example.com', 'Member')
        self.admin_user = ViewTestHelpers.create_user_with_role('admin@example.com', 'Admin')
        self.campus = Campus.objects.create(
            campus_name=CampusName.SB,
            campus_location='Hobart'
        )
        self.supervisor = Supervisor.objects.create(
            user=self.user,
            campus=self.campus
        )
        self.client = APIClient()
    
    def test_get_own_profile(self):
        """Test getting own user profile."""
        self.client.force_authenticate(user=self.user)
        url = reverse('accounts:profile_self')
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('user', response.data)
        self.assertIn('roles', response.data)
        self.assertIn('permissions', response.data)
        self.assertTrue(response.data['is_supervisor'])
        self.assertIn('supervisor_details', response.data)
    
    def test_admin_get_other_profile(self):
        """Test admin user getting another user's profile."""
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('accounts:profile_view', kwargs={'user_id': self.user.id})
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['email'], 'test@example.com')


class TokenEndpointsTestCase(APITestCase):
    """Test JWT token endpoints."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
    
    def test_token_obtain_pair(self):
        """Test obtaining JWT token pair."""
        url = reverse('accounts:token_obtain_pair')
        data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
    
    def test_token_refresh(self):
        """Test refreshing JWT token."""
        # First get tokens
        url = reverse('accounts:token_obtain_pair')
        data = {
            'email': 'test@example.com',
            'password': 'testpass123'
        }
        
        response = self.client.post(url, data)
        refresh_token = response.data['refresh']
        
        # Now refresh
        refresh_url = reverse('accounts:token_refresh')
        refresh_data = {
            'refresh': refresh_token
        }
        
        response = self.client.post(refresh_url, refresh_data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)