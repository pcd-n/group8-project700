import os
import pandas as pd
from django.core.management.base import BaseCommand
from django.db import transaction
from users.models import Role, Permission, RolePermission
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.text import Text


class Command(BaseCommand):
    help = 'Seed permissions and roles from CSV file (idempotent)'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.console = Console()

    def _is_permission_enabled(self, value):
        """Helper method to check if a permission is enabled, handling both boolean and string values"""
        if isinstance(value, bool):
            return value
        elif isinstance(value, str):
            return value.upper() == 'TRUE'
        else:
            return False

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default=None,
            help='Path to the permissions CSV file'
        )

    def handle(self, *args, **options):
        self.console.print(Panel.fit(
            "[bold blue]Web Tutors Backend - Permission Seeder[/bold blue]",
            border_style="blue"
        ))
        
        # Determine CSV file path
        if options['file']:
            csv_file = options['file']
        else:
            # Use absolute path to ensure it works from any directory
            # __file__ is at: users/management/commands/seed_permission.py
            # We want: users/management/permissions_matrix.csv
            # So we go up one directory from commands to management
            base_dir = os.path.dirname(os.path.dirname(__file__))
            csv_file = os.path.join(base_dir, 'permissions_matrix.csv')
        
        if not os.path.exists(csv_file):
            self.console.print(
                f"[bold red]✗ CSV file not found:[/bold red] {csv_file}"
            )
            return

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,
            ) as progress:
                
                # Read CSV with encoding fallback
                task = progress.add_task("Reading CSV file...", total=None)
                encodings_to_try = ['utf-8', 'utf-8-sig', 'latin1', 'cp1252']
                permission_data = None
                
                for encoding in encodings_to_try:
                    try:
                        # Read CSV and force boolean columns to be strings
                        permission_data = pd.read_csv(csv_file, encoding=encoding, dtype=str)
                        self.console.print(f"[green]✓ Successfully read CSV with encoding:[/green] {encoding}")
                        break
                    except UnicodeDecodeError:
                        continue
                
                if permission_data is None:
                    self.console.print("[bold red]✗ Could not read CSV with any encoding[/bold red]")
                    return

                progress.update(task, description="Processing CSV data...")

                # Get roles from columns (exclude 'resource', 'action', 'description')
                roles = permission_data.columns[2:-1].tolist()  # Skip 'resource', 'action', keep before 'description'
                
                self.console.print(f"[cyan]Found roles:[/cyan] {', '.join(roles)}")

                # Create permission entries (permission_key, description)
                permission_entries = [
                    (f"{row.resource}.{row.action}", row.description if pd.notna(row.description) else f"{row.action.title()} {row.resource}")
                    for row in permission_data.itertuples(index=False)
                ]

                # Create role-specific permission lists
                role_permissions = {}
                
                for role in roles:
                    role_permissions[role] = [
                        f"{row.resource}.{row.action}" 
                        for row in permission_data.itertuples(index=False) 
                        if self._is_permission_enabled(getattr(row, role, 'FALSE'))
                    ]

                progress.update(task, description="Creating permission breakdown table...")

            # Create permission breakdown table
            table = Table(title="Permission Breakdown by Role")
            table.add_column("Role", style="cyan", no_wrap=True)
            table.add_column("Permissions", style="magenta")
            table.add_column("Count", style="green", justify="right")

            for role, perms in role_permissions.items():
                table.add_row(role.title(), f"{len(perms)} permissions", str(len(perms)))

            self.console.print(table)

            # Start database operations in transaction
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=self.console,
            ) as progress:
                
                db_task = progress.add_task("Starting database operations...", total=None)
                
                with transaction.atomic():
                    # 1. Create/Update Roles (idempotent)
                    progress.update(db_task, description="Creating/updating roles...")
                    created_roles = {}
                    roles_created = 0
                    roles_updated = 0
                    
                    for role_name in roles:
                        role_title = role_name.title()
                        role, created = Role.objects.get_or_create(
                            role_name=role_title,
                            defaults={'description': f'{role_title} role with system-defined permissions'}
                        )
                        created_roles[role_name] = role
                        
                        if created:
                            roles_created += 1
                            self.console.print(f"[green]✓ Created role:[/green] {role_title}")
                        else:
                            roles_updated += 1
                            # Update description if needed
                            if not role.description:
                                role.description = f'{role_title} role with system-defined permissions'
                                role.save()
                            self.console.print(f"[yellow]• Role exists:[/yellow] {role_title}")

                    # 2. Create/Update Permissions (idempotent)
                    progress.update(db_task, description="Creating/updating permissions...")
                    created_permissions = {}
                    permissions_created = 0
                    permissions_updated = 0
                    
                    for permission_key, description in permission_entries:
                        permission, created = Permission.objects.get_or_create(
                            permission_key=permission_key,
                            defaults={'description': description}
                        )
                        created_permissions[permission_key] = permission
                        
                        if created:
                            permissions_created += 1
                            self.console.print(f"[green]✓ Created permission:[/green] {permission_key}")
                        else:
                            permissions_updated += 1
                            # Update description if it's different
                            if permission.description != description and description:
                                permission.description = description
                                permission.save()
                            self.console.print(f"[yellow]• Permission exists:[/yellow] {permission_key}")

                    # 3. Create/Update Role-Permission mappings (idempotent)
                    progress.update(db_task, description="Assigning permissions to roles...")
                    role_permission_assignments = 0
                    role_permission_removed = 0
                    
                    for role_name, permission_keys in role_permissions.items():
                        role = created_roles[role_name]
                        
                        # Get current permissions for this role
                        current_permissions = set(
                            RolePermission.objects.filter(role=role).values_list('permission__permission_key', flat=True)
                        )
                        new_permissions = set(permission_keys)
                        
                        # Add new permissions
                        permissions_to_add = new_permissions - current_permissions
                        for permission_key in permissions_to_add:
                            if permission_key in created_permissions:
                                permission = created_permissions[permission_key]
                                RolePermission.objects.get_or_create(role=role, permission=permission)
                                role_permission_assignments += 1
                                self.console.print(f"[green]✓ Assigned[/green] {permission_key} [green]to[/green] {role.role_name}")
                        
                        # Remove permissions that are no longer assigned
                        permissions_to_remove = current_permissions - new_permissions
                        for permission_key in permissions_to_remove:
                            try:
                                permission = Permission.objects.get(permission_key=permission_key)
                                RolePermission.objects.filter(role=role, permission=permission).delete()
                                role_permission_removed += 1
                                self.console.print(f"[red]✗ Removed[/red] {permission_key} [red]from[/red] {role.role_name}")
                            except Permission.DoesNotExist:
                                pass

            # Final summary panel
            summary_content = Text()
            summary_content.append("SEEDING COMPLETED SUCCESSFULLY!\n\n", style="bold green")
            summary_content.append(f"Roles created: {roles_created}\n", style="green")
            summary_content.append(f"Roles updated: {roles_updated}\n", style="yellow")
            summary_content.append(f"Permissions created: {permissions_created}\n", style="green")
            summary_content.append(f"Permissions updated: {permissions_updated}\n", style="yellow")
            summary_content.append(f"Role-permission assignments added: {role_permission_assignments}\n", style="green")
            summary_content.append(f"Role-permission assignments removed: {role_permission_removed}", style="red")

            self.console.print(Panel(summary_content, title="Summary", border_style="green"))

            # Show final role summary table
            summary_table = Table(title="Final Role Summary")
            summary_table.add_column("Role", style="cyan", no_wrap=True)
            summary_table.add_column("Total Permissions", style="magenta", justify="right")

            for role_name in roles:
                role = created_roles[role_name]
                permission_count = RolePermission.objects.filter(role=role).count()
                summary_table.add_row(role.role_name, str(permission_count))

            self.console.print(summary_table)

        except FileNotFoundError:
            self.console.print(f"[bold red]✗ CSV file not found:[/bold red] {csv_file}")
        except Exception as e:
            self.console.print(f"[bold red]✗ Error processing CSV file:[/bold red] {str(e)}")
