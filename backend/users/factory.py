"""
Factory classes for generating test data using Factory Boy and Faker.
"""
import factory
from factory.django import DjangoModelFactory
from factory.fuzzy import FuzzyChoice
from django.contrib.auth import get_user_model
from users.models import (
    Role, Permission, RolePermission, UserRoles, 
    Campus, CampusName, Supervisor
)

User = get_user_model()


class RoleFactory(DjangoModelFactory):
    """Factory for creating Role instances."""
    
    class Meta:
        model = Role
    
    role_name = factory.Sequence(lambda n: f"Role_{n}")
    description = factory.Faker('text', max_nb_chars=200)


class PermissionFactory(DjangoModelFactory):
    """Factory for creating Permission instances."""
    
    class Meta:
        model = Permission
    
    permission_key = factory.Sequence(lambda n: f"permission.{n}")
    description = factory.Faker('sentence', nb_words=6)


class CampusFactory(DjangoModelFactory):
    """Factory for creating Campus instances."""
    
    class Meta:
        model = Campus
    
    campus_name = FuzzyChoice([choice[0] for choice in CampusName.choices])
    campus_location = factory.LazyAttribute(lambda obj: {
        CampusName.SB: 'Hobart',
        CampusName.IR: 'Launceston', 
        CampusName.ONLINE: 'Online Campus'
    }.get(obj.campus_name, 'Unknown Location'))


class UserFactory(DjangoModelFactory):
    """Factory for creating User instances."""
    
    class Meta:
        model = User
    
    email = factory.Faker('email')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')
    is_active = True
    is_staff = False
    
    @factory.post_generation
    def password(self, create, extracted, **kwargs):
        """Set password for the user."""
        if not create:
            return
        password = extracted or 'defaultpass123'
        self.set_password(password)
        self.save()
    
    @classmethod
    def create_batch(cls, size, **kwargs):
        """Optimized batch creation."""
        users = []
        for i in range(size):
            user = cls.create(**kwargs)
            users.append(user)
        return users


class StaffUserFactory(UserFactory):
    """Factory for creating staff User instances."""
    
    is_staff = True


class SuperuserFactory(UserFactory):
    """Factory for creating superuser instances."""
    
    is_staff = True
    is_active = True


class UserRolesFactory(DjangoModelFactory):
    """Factory for creating UserRoles instances."""
    
    class Meta:
        model = UserRoles
    
    user = factory.SubFactory(UserFactory)
    role = factory.SubFactory(RoleFactory)
    is_active = True


class RolePermissionFactory(DjangoModelFactory):
    """Factory for creating RolePermission instances."""
    
    class Meta:
        model = RolePermission
        django_get_or_create = ('role', 'permission')
    
    role = factory.SubFactory(RoleFactory)
    permission = factory.SubFactory(PermissionFactory)


class SupervisorFactory(DjangoModelFactory):
    """Factory for creating Supervisor instances."""
    
    class Meta:
        model = Supervisor
    
    user = factory.SubFactory(UserFactory)
    campus = factory.SubFactory(CampusFactory)



# Predefined factories for common scenarios
class AdminUserFactory(UserFactory):
    """Factory for creating admin users with Admin role."""
    
    is_staff = True
    
    @factory.post_generation
    def roles(self, create, extracted, **kwargs):
        if not create:
            return
        
        admin_role, _ = Role.objects.get_or_create(
            role_name='Admin',
            defaults={'description': 'Administrator role'}
        )
        UserRoles.objects.create(user=self, role=admin_role)


class MemberUserFactory(UserFactory):
    """Factory for creating member users with Member role."""
    
    @factory.post_generation
    def roles(self, create, extracted, **kwargs):
        if not create:
            return
        
        member_role, _ = Role.objects.get_or_create(
            role_name='Member',
            defaults={'description': 'Member role'}
        )
        UserRoles.objects.create(user=self, role=member_role)


class TutorUserFactory(UserFactory):
    """Factory for creating tutor users with Tutor role."""
    
    @factory.post_generation
    def roles(self, create, extracted, **kwargs):
        if not create:
            return
        
        tutor_role, _ = Role.objects.get_or_create(
            role_name='Tutor',
            defaults={'description': 'Tutor role'}
        )
        UserRoles.objects.create(user=self, role=tutor_role)


class SupervisorUserFactory(UserFactory):
    """Factory for creating supervisor users with Supervisor role and campus."""
    
    @factory.post_generation
    def supervisor_profile(self, create, extracted, **kwargs):
        if not create:
            return
        
        # Create supervisor role
        supervisor_role, _ = Role.objects.get_or_create(
            role_name='Supervisor',
            defaults={'description': 'Supervisor role'}
        )
        UserRoles.objects.create(user=self, role=supervisor_role)
        
        # Create supervisor profile
        campus = CampusFactory()
        Supervisor.objects.create(user=self, campus=campus)


# Helper functions for creating test data
def create_test_permissions():
    """Create a set of test permissions."""
    permission_data = [
        ('can_create_users', 'Can create new users'),
        ('can_edit_users', 'Can edit existing users'),
        ('can_delete_users', 'Can delete users'),
        ('can_view_users', 'Can view user list'),
        ('can_manage_roles', 'Can manage user roles'),
        ('can_manage_permissions', 'Can manage permissions'),
        ('can_view_reports', 'Can view system reports'),
        ('can_manage_sessions', 'Can manage tutoring sessions'),
        ('can_view_students', 'Can view student information'),
        ('can_update_profile', 'Can update own profile'),
        ('can_book_sessions', 'Can book tutoring sessions'),
    ]
    
    permissions = []
    for key, description in permission_data:
        permission, _ = Permission.objects.get_or_create(
            permission_key=key,
            defaults={'description': description}
        )
        permissions.append(permission)
    
    return permissions


def create_test_roles_with_permissions():
    """Create test roles with appropriate permissions."""
    permissions = create_test_permissions()
    
    # Create Admin role with all permissions
    admin_role, _ = Role.objects.get_or_create(
        role_name='Admin',
        defaults={'description': 'System administrator with full access'}
    )
    
    # Create Supervisor role with management permissions
    supervisor_role, _ = Role.objects.get_or_create(
        role_name='Supervisor',
        defaults={'description': 'Supervisor with user management capabilities'}
    )
    
    # Create Tutor role with session management permissions
    tutor_role, _ = Role.objects.get_or_create(
        role_name='Tutor',
        defaults={'description': 'Tutor with session and student management'}
    )
    
    # Create Member role with basic permissions
    member_role, _ = Role.objects.get_or_create(
        role_name='Member',
        defaults={'description': 'Basic member with limited access'}
    )
    
    # Assign permissions to roles
    admin_permissions = permissions  # Admin gets all permissions
    supervisor_permissions = [p for p in permissions if 'users' in p.permission_key or 'view' in p.permission_key]
    tutor_permissions = [p for p in permissions if 'sessions' in p.permission_key or 'students' in p.permission_key or 'profile' in p.permission_key]
    member_permissions = [p for p in permissions if 'profile' in p.permission_key or 'book' in p.permission_key]
    
    # Create role-permission relationships
    for permission in admin_permissions:
        RolePermission.objects.get_or_create(role=admin_role, permission=permission)
    
    for permission in supervisor_permissions:
        RolePermission.objects.get_or_create(role=supervisor_role, permission=permission)
    
    for permission in tutor_permissions:
        RolePermission.objects.get_or_create(role=tutor_role, permission=permission)
    
    for permission in member_permissions:
        RolePermission.objects.get_or_create(role=member_role, permission=permission)
    
    return {
        'admin': admin_role,
        'supervisor': supervisor_role,
        'tutor': tutor_role,
        'member': member_role,
        'permissions': permissions
    }


class CompleteUserScenarioFactory:
    """Factory for creating complete user scenarios."""
    
    @staticmethod
    def create_user_with_role_and_permissions(role_name, permissions=None):
        """Create a user with a specific role and permissions."""
        if permissions is None:
            permissions = []
        
        # Create permissions
        permission_objects = []
        for perm_key in permissions:
            permission, _ = Permission.objects.get_or_create(
                permission_key=perm_key,
                defaults={'description': f'Permission for {perm_key}'}
            )
            permission_objects.append(permission)
        
        # Create role
        role, _ = Role.objects.get_or_create(
            role_name=role_name,
            defaults={'description': f'Role: {role_name}'}
        )
        
        # Assign permissions to role
        for permission in permission_objects:
            RolePermission.objects.get_or_create(role=role, permission=permission)
        
        # Create user
        user = UserFactory()
        UserRoles.objects.create(user=user, role=role)
        
        return {
            'user': user,
            'role': role,
            'permissions': permission_objects
        }
    
    @staticmethod
    def create_supervisor_with_campus():
        """Create a supervisor user with campus assignment."""
        campus = CampusFactory()
        user = UserFactory()
        
        # Create supervisor role
        supervisor_role, _ = Role.objects.get_or_create(
            role_name='Supervisor',
            defaults={'description': 'Supervisor role'}
        )
        
        # Assign role to user
        UserRoles.objects.create(user=user, role=supervisor_role)
        
        # Create supervisor profile
        supervisor = Supervisor.objects.create(user=user, campus=campus)
        
        return {
            'user': user,
            'supervisor': supervisor,
            'campus': campus
        }
    
    @staticmethod
    def create_test_organization():
        """Create a complete test organization with multiple users and roles."""
        # Create campuses
        campuses = [
            CampusFactory(campus_name=CampusName.SB),
            CampusFactory(campus_name=CampusName.IR),
            CampusFactory(campus_name=CampusName.ONLINE)
        ]
        
        # Create roles and permissions
        roles_data = create_test_roles_with_permissions()
        
        # Create admin user
        admin = AdminUserFactory()
        
        # Create supervisors (one for each physical campus)
        supervisors = []
        for campus in campuses[:2]:  # Skip online campus for supervisors
            supervisor_user = UserFactory()
            supervisor_role = roles_data['supervisor']
            UserRoles.objects.create(user=supervisor_user, role=supervisor_role)
            Supervisor.objects.create(user=supervisor_user, campus=campus)
            supervisors.append(supervisor_user)
        
        # Create tutors
        tutors = []
        for _ in range(5):
            tutor = TutorUserFactory()
            tutors.append(tutor)
        
        # Create members
        members = []
        for _ in range(10):
            member = MemberUserFactory()
            members.append(member)
        
        return {
            'campuses': campuses,
            'roles': roles_data,
            'admin': admin,
            'supervisors': supervisors,
            'tutors': tutors,
            'members': members
        }
