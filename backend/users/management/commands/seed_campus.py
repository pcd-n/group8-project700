"""
Django management command to seed campus data.
Usage: python manage.py seed_campus
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from users.models import Campus, CampusName
from rich.console import Console
from rich.table import Table
from rich.panel import Panel


class Command(BaseCommand):
    help = 'Seed campus data with HOBART (SB), LAUNCESTON (IR), and ONLINE campuses'
    
    def __init__(self):
        super().__init__()
        self.console = Console()
    
    def handle(self, *args, **options):
        """Main command handler."""
        self.console.print(Panel.fit("[bold blue]Campus Seed Command[/bold blue]", 
                                   subtitle="Loading campus data into database"))
        
        # Campus data to seed
        campus_data = [
            {
                'campus_name': CampusName.SB,
                'campus_location': 'Hobart, Tasmania, Australia'
            },
            {
                'campus_name': CampusName.IR, 
                'campus_location': 'Launceston, Tasmania, Australia'
            },
            {
                'campus_name': CampusName.ONLINE,
                'campus_location': 'Online Virtual Campus'
            }
        ]
        
        created_campuses = []
        updated_campuses = []
        
        try:
            with transaction.atomic():
                for data in campus_data:
                    campus, created = Campus.objects.get_or_create(
                        campus_name=data['campus_name'],
                        defaults={
                            'campus_location': data['campus_location']
                        }
                    )
                    
                    if created:
                        created_campuses.append(campus)
                        self.console.print(f"[green]✓ Created campus:[/green] {campus.campus_name}")
                        self.stdout.write(
                            self.style.SUCCESS(f'Created campus: {campus.campus_name}')
                        )
                    else:
                        # Update location if it's different
                        if campus.campus_location != data['campus_location']:
                            campus.campus_location = data['campus_location']
                            campus.save()
                            updated_campuses.append(campus)
                            self.console.print(f"[yellow]⚠ Updated campus:[/yellow] {campus.campus_name}")
                            self.stdout.write(
                                self.style.WARNING(f'Updated campus: {campus.campus_name}')
                            )
                        else:
                            self.console.print(f"[blue]ℹ Campus already exists:[/blue] {campus.campus_name}")
                            self.stdout.write(
                                self.style.NOTICE(f'Campus already exists: {campus.campus_name}')
                            )
            
            # Display results in a table
            table = Table(title="Campus Seed Results")
            table.add_column("Campus Code", style="cyan", no_wrap=True)
            table.add_column("Campus Name", style="magenta")
            table.add_column("Location", style="white")
            table.add_column("Status", style="green")
            
            all_campuses = Campus.objects.all().order_by('campus_name')
            for campus in all_campuses:
                if campus in created_campuses:
                    status = "[green]Created[/green]"
                elif campus in updated_campuses:
                    status = "[yellow]Updated[/yellow]"
                else:
                    status = "[blue]Exists[/blue]"
                
                table.add_row(
                    campus.campus_name,
                    campus.get_campus_name_display(),
                    campus.campus_location,
                    status
                )
            
            self.console.print(table)
            
            # Summary
            total = all_campuses.count()
            created_count = len(created_campuses)
            updated_count = len(updated_campuses)
            
            self.console.print("\n[bold green]✓ Campus seeding completed successfully![/bold green]")
            self.console.print(f"Total campuses: {total}")
            self.console.print(f"Created: {created_count}")
            self.console.print(f"Updated: {updated_count}")
            self.console.print(f"Already existed: {total - created_count - updated_count}")
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'Successfully seeded {created_count} new campuses, '
                    f'updated {updated_count} campuses. Total: {total} campuses.'
                )
            )
            
        except Exception as e:
            self.console.print(f"[bold red]✗ Error seeding campuses:[/bold red] {str(e)}")
            self.stdout.write(
                self.style.ERROR(f'Error seeding campuses: {str(e)}')
            )
            raise
