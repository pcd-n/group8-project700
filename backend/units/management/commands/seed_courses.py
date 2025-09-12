from django.core.management.base import BaseCommand
from django.db import transaction
from units.models import Unit, Course
from users.models import Campus
from rich.console import Console
from rich.table import Table

console = Console()


class Command(BaseCommand):
    help = 'Seed courses from timetable data'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Run without making changes to the database',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            console.print("[yellow]Running in DRY RUN mode - no changes will be made[/yellow]")
        
        # Extract unique units from the timetable data
        units_data = {
            'KIT101': 'Programming Fundamentals',
            'KIT103': 'Computational Science', 
            'KIT107': 'Programming',
            'KIT111': 'Data Networks and Security',
            'KIT119': 'Database Fundamentals',
            'KIT203': 'ICT Project Management and Modelling',
            'KIT208': 'Virtual and Mixed Reality Technology',
            'KIT213': 'Operating Systems',
            'KIT214': 'Intelligent and Secure Web Development',
            'KIT219': 'Development Methodologies and User Experience',
            'KIT300': 'ICT Project',
            'KIT307': 'Computer Graphics and Animation: Principles and Programming',
            'KIT312': 'Information Systems Management',
            'KIT315': 'Machine Learning and Applications',
            'KIT325': 'Advanced CyberSecurity and eForensics',
            'KIT500': 'Programming Foundation',
            'KIT501': 'ICT Systems Administration Fundamentals',
            'KIT502': 'Web Development',
            'KIT514': 'Secure Web and Cloud Development',
            'KIT519': 'Software Engineering and HCI',
            'KIT700': 'ICT Systems Project',
            'KIT714': 'ICT Research Principles',
            'KIT718': 'Big Data Analytics',
            'KIT719': 'Natural Language Processing and Generative AI',
            'KIT725': 'Cybersecurity and eForensics',
            'KIT726': 'System Administration and Security Assurance',
            'KIT728': 'Software Testing and Quality Management',
            'KIT730': 'Business Process Innovation',
        }

        # Define course structures based on unit levels
        courses_data = {
            'BIT-H': {
                'name': 'Bachelor of Information Technology - Hobart',
                'campus': 'SB'
            },
            'BIT-L': {
                'name': 'Bachelor of Information Technology - Launceston', 
                'campus': 'IR'
            },
            'GC-ICT-H': {
                'name': 'Graduate Certificate in ICT - Hobart',
                'campus': 'SB'
            },
            'MIT-H': {
                'name': 'Master of Information Technology - Hobart',
                'campus': 'SB'
            },
            'MIT-L': {
                'name': 'Master of Information Technology - Launceston',
                'campus': 'IR'
            }
        }

        console.print(f"[green]Found {len(units_data)} units and {len(courses_data)} courses to process[/green]")
        
        if not dry_run:
            with transaction.atomic():
                self._create_units(units_data)
                self._create_courses(courses_data)
        else:
            self._display_preview(units_data, courses_data)

    def _create_units(self, units_data):
        """Create unit records."""
        console.print("[cyan]Creating Units...[/cyan]")
        
        created_count = 0
        updated_count = 0
        
        for unit_code, unit_name in units_data.items():
            # Determine standard credit points based on unit level
            unit_number = int(unit_code[3:])
            if 100 <= unit_number <= 399:
                credits = 12.5  # Undergraduate units
            elif 500 <= unit_number <= 599:
                credits = 12.5  # Graduate Certificate units
            elif 700 <= unit_number <= 799:
                credits = 25    # Masters units
            else:
                credits = 12.5  # Default
            
            unit, created = Unit.objects.get_or_create(
                unit_code=unit_code,
                defaults={
                    'unit_name': unit_name,
                    'credits': credits
                }
            )
            
            if created:
                created_count += 1
                console.print(f"[green]✓[/green] Created unit: {unit_code} - {unit_name} ({credits} credits)")
            else:
                # Update unit name and credits if different
                updated = False
                if unit.unit_name != unit_name:
                    unit.unit_name = unit_name
                    updated = True
                if unit.credits != credits:
                    unit.credits = credits
                    updated = True
                
                if updated:
                    unit.save()
                    updated_count += 1
                    console.print(f"[yellow]↻[/yellow] Updated unit: {unit_code} - {unit_name} ({credits} credits)")
        
        console.print(f"[green]Units: {created_count} created, {updated_count} updated[/green]")

    def _create_courses(self, courses_data):
        """Create course records."""
        console.print("[cyan]Creating Courses...[/cyan]")
        
        created_count = 0
        updated_count = 0
        
        for course_code, course_info in courses_data.items():
            # Get campus if specified
            campus = None
            if course_info['campus'] and course_info['campus'] != 'ONLINE':
                try:
                    campus = Campus.objects.get(campus_name=course_info['campus'])
                except Campus.DoesNotExist:
                    console.print(f"[red]Warning: Campus {course_info['campus']} not found[/red]")
            
            course, created = Course.objects.get_or_create(
                course_code=course_code,
                defaults={
                    'course_name': course_info['name'],
                    'campus': campus
                }
            )
            
            if created:
                created_count += 1
                campus_display = course_info['campus'] if course_info['campus'] else 'No specific campus'
                console.print(f"[green]✓[/green] Created course: {course_code} - {course_info['name']} ({campus_display})")
            else:
                # Update course if needed
                updated = False
                if course.course_name != course_info['name']:
                    course.course_name = course_info['name']
                    updated = True
                if course.campus != campus:
                    course.campus = campus
                    updated = True
                
                if updated:
                    course.save()
                    updated_count += 1
                    campus_display = course_info['campus'] if course_info['campus'] else 'No specific campus'
                    console.print(f"[yellow]↻[/yellow] Updated course: {course_code} - {course_info['name']} ({campus_display})")
        
        console.print(f"[green]Courses: {created_count} created, {updated_count} updated[/green]")

    def _display_preview(self, units_data, courses_data):
        """Display preview of what would be created."""
        console.print("[cyan]PREVIEW MODE - What would be created:[/cyan]")
        
        # Units table
        units_table = Table(title="Units to be Created/Updated")
        units_table.add_column("Unit Code", style="cyan")
        units_table.add_column("Unit Name", style="green")
        units_table.add_column("Credits", style="yellow")
        
        for unit_code, unit_name in sorted(units_data.items()):
            # Determine credits
            unit_number = int(unit_code[3:])
            if 100 <= unit_number <= 399:
                credits = "12.5"
            elif 500 <= unit_number <= 599:
                credits = "12.5"
            elif 700 <= unit_number <= 799:
                credits = "25"
            else:
                credits = "12.5"
            
            units_table.add_row(unit_code, unit_name, credits)
        
        console.print(units_table)
        
        # Courses table
        courses_table = Table(title="Courses to be Created/Updated")
        courses_table.add_column("Course Code", style="cyan")
        courses_table.add_column("Course Name", style="green")
        courses_table.add_column("Campus", style="yellow")
        
        for course_code, course_info in sorted(courses_data.items()):
            campus_display = course_info['campus'] if course_info['campus'] else 'No specific campus'
            courses_table.add_row(course_code, course_info['name'], campus_display)
        
        console.print(courses_table)
        
        console.print(f"\n[yellow]Total: {len(units_data)} units and {len(courses_data)} courses would be processed[/yellow]")
        console.print("[cyan]Run without --dry-run to apply changes[/cyan]")
