from django.core.management.base import BaseCommand, CommandError
from users.models import User, Role
from rich.console import Console


class Command(BaseCommand):
    help = 'Assign or remove roles from users'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.console = Console()

    def add_arguments(self, parser):
        parser.add_argument('email', type=str, help='User email address')
        parser.add_argument('role', type=str, help='Role name to assign or remove')
        parser.add_argument(
            '--remove',
            action='store_true',
            help='Remove the role instead of assigning it',
        )

    def handle(self, *args, **options):
        email = options['email']
        role_name = options['role']
        is_remove = options['remove']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise CommandError(f'User with email "{email}" does not exist')

        try:
            role = Role.objects.get(role_name=role_name)
        except Role.DoesNotExist:
            available_roles = ', '.join(Role.objects.values_list('role_name', flat=True))
            raise CommandError(f'Role "{role_name}" does not exist. Available roles: {available_roles}')

        if is_remove:
            # Remove role
            if user.remove_role(role_name):
                self.console.print(f"[green]✓ Successfully removed role '{role_name}' from user '{email}'[/green]")
            else:
                self.console.print(f"[yellow]• User '{email}' does not have active role '{role_name}'[/yellow]")
        else:
            # Assign role
            try:
                user.assign_role(role_name)
                self.console.print(f"[green]✓ Successfully assigned role '{role_name}' to user '{email}'[/green]")
            except ValueError as e:
                raise CommandError(str(e))

        # Show user's current roles
        current_roles = [role.role_name for role in user.get_user_roles()]
        self.console.print(f"[cyan]Current roles for {email}: {', '.join(current_roles) if current_roles else 'None'}[/cyan]")
