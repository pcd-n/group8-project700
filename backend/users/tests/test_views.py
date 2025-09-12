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
    
    def test_login_missing_email(self):
        """Test login with missing email."""
        data = {'password': 'testpass123'}
        
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_login_missing_password(self):
        """Test login with missing password."""
        data = {'email': 'test@example.com'}
        
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_login_invalid_credentials(self):
        """Test login with invalid credentials."""
        data = {
            'email': 'test@example.com',
            'password': 'wrongpassword'
        }
        
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
    
    def test_login_nonexistent_user(self):
        """Test login with non-existent user."""
        data = {
            'email': 'nonexistent@example.com',
            'password': 'testpass123'
        }
        
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)
    
    def test_login_inactive_user(self):
        """Test login with inactive user."""
        self.user.is_active = False
        self.user.save()
        
        data = {
            'email': 'test@example.com',
            'password': 'testpass123'
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
        Role.objects.create(role_name='Member', description='Default member role')
        Role.objects.create(role_name='TestRole', description='Test role')
    
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
            'roles': ['TestRole']
        }
        
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email='newuser@example.com')
        self.assertTrue(user.has_role('TestRole'))
    
    def test_registration_as_supervisor(self):
        """Test registration with supervisor creation."""
        data = {
            'email': 'supervisor@example.com',
            'password': 'newpass123',
            'first_name': 'Super',
            'last_name': 'Visor',
            'is_supervisor': True,
            'campus_id': self.campus.id
        }
        
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['is_supervisor'])
        
        user = User.objects.get(email='supervisor@example.com')
        self.assertTrue(hasattr(user, 'supervisor'))
        self.assertEqual(user.supervisor.campus, self.campus)
    
    def test_registration_invalid_data(self):
        """Test registration with invalid data."""
        data = {
            'email': 'invalid-email',
            'password': 'short'
        }
        
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_registration_existing_email(self):
        """Test registration with existing email."""
        User.objects.create_user(email='existing@example.com')
        
        data = {
            'email': 'existing@example.com',
            'password': 'newpass123'
        }
        
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
    
    def test_bulk_registration(self):
        """Test bulk user registration."""
        data = [
            {
                'email': 'user1@example.com',
                'password': 'password123',
                'first_name': 'User1'
            },
            {
                'email': 'user2@example.com',
                'password': 'password123',
                'first_name': 'User2'
            }
        ]
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['success_count'], 2)
        self.assertEqual(response.data['error_count'], 0)
    
    def test_bulk_registration_with_errors(self):
        """Test bulk registration with some errors."""
        User.objects.create_user(email='existing@example.com')
        
        data = [
            {
                'email': 'user1@example.com',
                'password': 'password123',
                'first_name': 'User1'
            },
            {
                'email': 'existing@example.com',  # Already exists
                'password': 'password123',
                'first_name': 'Existing'
            }
        ]
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['success_count'], 1)
        self.assertEqual(response.data['error_count'], 1)


class UserUpdateViewTestCase(APITestCase):
    """Test cases for UserUpdateView."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User'
        )
        self.staff_user = User.objects.create_user(
            email='staff@example.com',
            password='staffpass123',
            is_staff=True
        )
        self.other_user = User.objects.create_user(
            email='other@example.com',
            password='otherpass123'
        )
        self.url = reverse('accounts:user_update_self')
        self.client = APIClient()
    
    def test_user_update_own_profile(self):
        """Test user updating their own profile."""
        self.client.force_authenticate(user=self.user)
        
        data = {
            'first_name': 'Updated',
            'last_name': 'Name'
        }
        
        response = self.client.put(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'Updated')
        self.assertEqual(self.user.last_name, 'Name')
    
    def test_staff_update_other_user(self):
        """Test staff user updating another user."""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('accounts:user_update', kwargs={'user_id': self.user.id})
        
        data = {
            'first_name': 'StaffUpdated',
            'is_active': False
        }
        
        response = self.client.put(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'StaffUpdated')
        self.assertFalse(self.user.is_active)
    
    def test_user_update_other_user_forbidden(self):
        """Test user trying to update another user (forbidden)."""
        self.client.force_authenticate(user=self.user)
        url = reverse('accounts:user_update', kwargs={'user_id': self.other_user.id})
        
        data = {'first_name': 'Forbidden'}
        
        response = self.client.put(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_update_nonexistent_user(self):
        """Test updating non-existent user."""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('accounts:user_update', kwargs={'user_id': 999})
        
        data = {'first_name': 'Test'}
        
        response = self.client.put(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_unauthenticated_update(self):
        """Test updating without authentication."""
        data = {'first_name': 'Test'}
        
        response = self.client.put(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
    
    def test_partial_update(self):
        """Test partial update using PATCH."""
        self.client.force_authenticate(user=self.user)
        
        data = {'first_name': 'PartialUpdate'}
        
        response = self.client.patch(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, 'PartialUpdate')
        self.assertEqual(self.user.last_name, 'User')  # Unchanged
    
    def test_bulk_update(self):
        """Test bulk user updates."""
        self.client.force_authenticate(user=self.staff_user)
        
        data = [
            {
                'id': self.user.id,
                'first_name': 'BulkUpdated1'
            },
            {
                'id': self.other_user.id,
                'first_name': 'BulkUpdated2'
            }
        ]
        
        response = self.client.patch(reverse('accounts:bulk_user_update'), data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['success_count'], 2)
        self.assertEqual(response.data['error_count'], 0)


class RoleListCreateViewTestCase(APITestCase):
    """Test cases for RoleListCreateView."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.role = Role.objects.create(role_name='ExistingRole')
        self.url = reverse('accounts:roles_list_create')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_list_roles(self):
        """Test listing all roles."""
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Handle both list and paginated responses
        data = response.data
        if isinstance(data, dict) and 'results' in data:
            data = data['results']
        # Check that our test role exists
        role_names = [r['role_name'] for r in data]
        self.assertIn('ExistingRole', role_names)
    
    def test_create_role(self):
        """Test creating a new role."""
        data = {
            'role_name': 'NewRole',
            'description': 'A new role'
        }
        
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['role_name'], 'NewRole')
        self.assertTrue(Role.objects.filter(role_name='NewRole').exists())
    
    def test_create_duplicate_role(self):
        """Test creating a role with duplicate name."""
        data = {
            'role_name': 'ExistingRole',
            'description': 'Duplicate role'
        }
        
        response = self.client.post(self.url, data)
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_bulk_create_roles(self):
        """Test bulk role creation."""
        data = [
            {
                'role_name': 'Role1',
                'description': 'First role'
            },
            {
                'role_name': 'Role2',
                'description': 'Second role'
            }
        ]
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['success_count'], 2)
        self.assertEqual(response.data['error_count'], 0)
    
    def test_unauthenticated_access(self):
        """Test accessing without authentication."""
        self.client.force_authenticate(user=None)
        
        response = self.client.get(self.url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class UserRolesViewTestCase(APITestCase):
    """Test cases for UserRolesView."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.role = Role.objects.create(role_name='TestRole')
        # Use the proper role assignment method instead of direct creation
        User.objects._assign_role_to_user(self.user, 'TestRole')
        # Store reference to the user role for tests that need it
        self.user_role = UserRoles.objects.get(user=self.user, role=self.role)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_get_user_roles(self):
        """Test getting roles for a specific user."""
        url = reverse('accounts:user_roles_detail', kwargs={'user_id': self.user.id})
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('user', response.data)
        self.assertIn('roles', response.data)
        # User should have only 1 active role (TestRole, Member should be disabled)
        active_roles = [r for r in response.data['roles'] if r.get('is_active', True)]
        self.assertEqual(len(active_roles), 1)
    
    def test_get_all_user_roles(self):
        """Test getting all user-role assignments."""
        url = reverse('accounts:user_roles_list')
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should have total user-role records (including disabled Member role)
        self.assertGreaterEqual(len(response.data), 1)
    
    def test_assign_single_role(self):
        """Test assigning a role to a user."""
        new_role = Role.objects.create(role_name='NewRole')
        url = reverse('accounts:user_roles_list')
        
        data = {
            'user_id': self.user.id,
            'role_id': new_role.id
        }
        
        response = self.client.post(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Check that old role is disabled and new role is active
        self.assertFalse(UserRoles.objects.get(user=self.user, role=self.role).is_active)
        self.assertTrue(UserRoles.objects.get(user=self.user, role=new_role).is_active)
    
    def test_bulk_assign_roles(self):
        """Test bulk role assignments."""
        user2 = User.objects.create_user(email='user2@example.com')
        role2 = Role.objects.create(role_name='Role2')
        url = reverse('accounts:user_roles_list')
        
        data = [
            {
                'user_id': self.user.id,
                'role_id': role2.id
            },
            {
                'user_id': user2.id,
                'role_id': self.role.id
            }
        ]
        
        response = self.client.post(url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['success_count'], 2)
    
    def test_update_user_roles(self):
        """Test updating all roles for a user."""
        new_role = Role.objects.create(role_name='NewRole')
        url = reverse('accounts:user_roles_update', kwargs={'user_id': self.user.id})
        
        data = {'role_ids': [new_role.id]}
        
        response = self.client.put(url, data)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check that old role is disabled and new role is active
        self.assertFalse(UserRoles.objects.get(user=self.user, role=self.role).is_active)
        self.assertTrue(UserRoles.objects.get(user=self.user, role=new_role).is_active)
    
    def test_disable_user_role(self):
        """Test disabling a specific user role assignment."""
        url = reverse('accounts:user_role_disable', kwargs={
            'user_id': self.user.id,
            'role_id': self.role.id
        })
        
        response = self.client.delete(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user_role.refresh_from_db()
        self.assertFalse(self.user_role.is_active)
    
    def test_get_nonexistent_user_roles(self):
        """Test getting roles for non-existent user."""
        url = reverse('accounts:user_roles_detail', kwargs={'user_id': 999})
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class UserProfileViewTestCase(APITestCase):
    """Test cases for UserProfileView."""
    
    def setUp(self):
        """Set up test data."""
        self.role = Role.objects.create(role_name='TestRole')
        self.permission = Permission.objects.create(permission_key='test.permission')
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123',
            first_name='Test',
            last_name='User',
            role_name='TestRole'
        )
        self.staff_user = User.objects.create_user(
            email='staff@example.com',
            password='staffpass123',
            is_staff=True
        )
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
        url = reverse('accounts:profile')
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('user', response.data)
        self.assertIn('roles', response.data)
        self.assertIn('permissions', response.data)
        self.assertTrue(response.data['is_supervisor'])
        self.assertIn('supervisor_details', response.data)
    
    def test_staff_get_other_profile(self):
        """Test staff user getting another user's profile."""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('accounts:user_profile', kwargs={'user_id': self.user.id})
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['user']['email'], 'test@example.com')
    
    def test_user_get_other_profile_forbidden(self):
        """Test user trying to get another user's profile (forbidden)."""
        other_user = User.objects.create_user(email='other@example.com')
        self.client.force_authenticate(user=self.user)
        url = reverse('accounts:user_profile', kwargs={'user_id': other_user.id})
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
    
    def test_get_nonexistent_user_profile(self):
        """Test getting profile for non-existent user."""
        self.client.force_authenticate(user=self.staff_user)
        url = reverse('accounts:user_profile', kwargs={'user_id': 999})
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
    
    def test_unauthenticated_profile_access(self):
        """Test accessing profile without authentication."""
        url = reverse('accounts:profile')
        
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class PermissionListCreateViewTestCase(APITestCase):
    """Test cases for PermissionListCreateView."""
    
    def setUp(self):
        """Set up test data."""
        self.user = User.objects.create_user(
            email='test@example.com',
            password='testpass123'
        )
        self.permission = Permission.objects.create(permission_key='existing.permission')
        self.url = reverse('accounts:permissions_list_create')
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
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
    
    def test_bulk_create_permissions(self):
        """Test bulk permission creation."""
        data = [
            {
                'permission_key': 'permission1',
                'description': 'First permission'
            },
            {
                'permission_key': 'permission2',
                'description': 'Second permission'
            }
        ]
        
        response = self.client.post(self.url, data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['success_count'], 2)
        self.assertEqual(response.data['error_count'], 0)
