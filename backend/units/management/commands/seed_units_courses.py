from django.core.management.base import BaseCommand
from django.db import transaction
from units.models import Unit, Course, UnitCourse
from users.models import Campus
from rich.console import Console
from rich.table import Table
from rich.progress import Progress
import re

console = Console()


class Command(BaseCommand):
    help = 'Seed units and courses from timetable CSV data'

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
        
        # Data extracted from the CSV
        timetable_data = [
            ("KIT101_H_SEM2_I", "Programming Fundamentals", "SAA-313"),
            ("KIT101_L_SEM2_I", "Programming Fundamentals", "SAA-313"),
            ("KIT103_H_SEM2_I", "Computational Science", "SAA-313"),
            ("KIT103_L_SEM2_I", "Computational Science", "SAA-313"),
            ("KIT107_H_SEM2_I", "Programming", "SAA-313"),
            ("KIT107_L_SEM2_I", "Programming", "SAA-313"),
            ("KIT111_H_SEM2_I", "Data Networks and Security", "SAA-313"),
            ("KIT111_L_SEM2_I", "Data Networks and Security", "SAA-313"),
            ("KIT119_H_SEM2_I", "Database Fundamentals", "SAA-313"),
            ("KIT119_L_SEM2_I", "Database Fundamentals", "SAA-313"),
            ("KIT203_H_SPR_I", "ICT Project Management and Modelling", "SAA-313"),
            ("KIT203_L_SPR_I", "ICT Project Management and Modelling", "SAA-313"),
            ("KIT208_H_SEM2_I", "Virtual and Mixed Reality Technology", "SAA-313"),
            ("KIT208_L_SEM2_I", "Virtual and Mixed Reality Technology", "SAA-313"),
            ("KIT213_H_SEM2_I", "Operating Systems", "SAA-313"),
            ("KIT213_L_SEM2_I", "Operating Systems", "SAA-313"),
            ("KIT214_H_SEM2_I", "Intelligent and Secure Web Development", "SAA-313"),
            ("KIT214_L_SEM2_I", "Intelligent and Secure Web Development", "SAA-313"),
            ("KIT219_H_SEM2_I", "Development Methodologies and User Experience", "SAA-313"),
            ("KIT219_L_SEM2_I", "Development Methodologies and User Experience", "SAA-313"),
            ("KIT300_H_SEM2_I", "ICT Project", "SAA-313"),
            ("KIT300_L_SEM2_I", "ICT Project", "SAA-313"),
            ("KIT307_H_SEM2_I", "Computer Graphics and Animation: Principles and Programming", "SAA-313"),
            ("KIT307_L_SEM2_I", "Computer Graphics and Animation: Principles and Programming", "SAA-313"),
            ("KIT312_H_SEM2_I", "Information Systems Management", "SAA-313"),
            ("KIT315_H_SEM2_I", "Machine Learning and Applications", "SAA-313"),
            ("KIT315_L_SEM2_I", "Machine Learning and Applications", "SAA-313"),
            ("KIT325_H_SEM2_I", "Advanced CyberSecurity and eForensics", "SAA-313"),
            ("KIT325_L_SEM2_I", "Advanced CyberSecurity and eForensics", "SAA-313"),
            ("KIT500_H_SEM2_I", "Programming Foundation", "SAA-313"),
            ("KIT501_H_SEM2_I", "ICT Systems Administration Fundamentals", "SAA-313"),
            ("KIT502_H_SEM2_I", "Web Development", "SAA-313"),
            ("KIT514_H_SEM2_I", "Secure Web and Cloud Development", "SAA-313"),
            ("KIT514_L_SEM2_I", "Secure Web and Cloud Development", "SAA-313"),
            ("KIT519_H_SEM2_I", "Software Engineering and HCI", "SAA-313"),
            ("KIT519_L_SEM2_I", "Software Engineering and HCI", "SAA-313"),
            ("KIT700_H_SEM2_I", "ICT Systems Project", "SAA-313"),
            ("KIT700_L_SEM2_I", "ICT Systems Project", "SAA-313"),
            ("KIT714_H_SEM2_I", "ICT Research Principles", "SAA-313"),
            ("KIT714_L_SEM2_I", "ICT Research Principles", "SAA-313"),
            ("KIT718_H_SEM2_I", "Big Data Analytics", "SAA-313"),
            ("KIT718_L_SEM2_I", "Big Data Analytics", "SAA-313"),
            ("KIT719_H_SEM2_I", "Natural Language Processing and Generative AI", "SAA-313"),
            ("KIT719_L_SEM2_I", "Natural Language Processing and Generative AI", "SAA-313"),
            ("KIT725_H_SEM2_I", "Cybersecurity and eForensics", "SAA-313"),
            ("KIT726_H_SEM2_I", "System Administration and Security Assurance", "SAA-313"),
            ("KIT728_H_SEM2_I", "Software Testing and Quality Management", "SAA-313"),
            ("KIT728_L_SEM2_I", "Software Testing and Quality Management", "SAA-313"),
            ("KIT730_H_SEM2_I", "Business Process Innovation", "SAA-313"),
        ]
        
        # Extract unique units
        units_data = {}
        courses_data = {}
        
        for subject_code, subject_description, faculty in timetable_data:
            # Extract unit code (e.g., KIT101 from KIT101_H_SEM2_I)
            unit_code_match = re.match(r'^([A-Z]+\d+)', subject_code)
            if unit_code_match:
                unit_code = unit_code_match.group(1)
                units_data[unit_code] = subject_description
                
                # Determine course information
                if unit_code.startswith('KIT'):
                    # Determine level and type from the subject code
                    if 'H' in subject_code:
                        campus_code = 'H'  # Hobart
                        campus_name = 'SB'
                    elif 'L' in subject_code:
                        campus_code = 'L'  # Launceston
                        campus_name = 'IR'
                    else:
                        campus_code = 'O'  # Online
                        campus_name = 'ONLINE'
                    
                    # Determine course level
                    unit_number = int(unit_code[3:])  # Extract number part (e.g., 101 from KIT101)
                    
                    if 100 <= unit_number <= 199:
                        level = "Undergraduate Year 1"
                        course_code = "BIT"
                    elif 200 <= unit_number <= 399:
                        level = "Undergraduate Year 2-3"
                        course_code = "BIT"
                    elif 500 <= unit_number <= 599:
                        level = "Graduate Certificate/Diploma"
                        course_code = "GC-ICT"
                    elif 700 <= unit_number <= 799:
                        level = "Masters"
                        course_code = "MIT"
                    else:
                        level = "Undergraduate"
                        course_code = "BIT"
                    
                    # Create course entry
                    full_course_code = f"{course_code}-{campus_code}"
                    course_name = f"Information Technology ({level}) - {campus_name}"
                    courses_data[full_course_code] = {
                        'name': course_name,
                        'campus': campus_name,
                        'level': level
                    }

        console.print(f"[green]Found {len(units_data)} unique units and {len(courses_data)} course variations[/green]")
        
        if not dry_run:
            with transaction.atomic():
                self._create_units(units_data)
                self._create_courses(courses_data)
                self._create_unit_courses(timetable_data)
        else:
            self._display_preview(units_data, courses_data)

    def _create_units(self, units_data):
        """Create unit records."""
        console.print("[cyan]Creating Units...[/cyan]")
        
        created_count = 0
        updated_count = 0
        
        with Progress() as progress:
            task = progress.add_task("Creating units...", total=len(units_data))
            
            for unit_code, unit_name in units_data.items():
                unit, created = Unit.objects.get_or_create(
                    unit_code=unit_code,
                    defaults={
                        'unit_name': unit_name,
                        'credits': 12.5  # Standard credit points for KIT units
                    }
                )
                
                if created:
                    created_count += 1
                    console.print(f"[green]✓[/green] Created unit: {unit_code} - {unit_name}")
                else:
                    # Update unit name if different
                    if unit.unit_name != unit_name:
                        unit.unit_name = unit_name
                        unit.save()
                        updated_count += 1
                        console.print(f"[yellow]↻[/yellow] Updated unit: {unit_code} - {unit_name}")
                
                progress.advance(task)
        
        console.print(f"[green]Units: {created_count} created, {updated_count} updated[/green]")

    def _create_courses(self, courses_data):
        """Create course records."""
        console.print("[cyan]Creating Courses...[/cyan]")
        
        created_count = 0
        updated_count = 0
        
        with Progress() as progress:
            task = progress.add_task("Creating courses...", total=len(courses_data))
            
            for course_code, course_info in courses_data.items():
                # Get campus
                campus = None
                if course_info['campus'] != 'ONLINE':
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
                    console.print(f"[green]✓[/green] Created course: {course_code} - {course_info['name']}")
                else:
                    # Update course if needed
                    if course.course_name != course_info['name']:
                        course.course_name = course_info['name']
                        course.campus = campus
                        course.save()
                        updated_count += 1
                        console.print(f"[yellow]↻[/yellow] Updated course: {course_code} - {course_info['name']}")
                
                progress.advance(task)
        
        console.print(f"[green]Courses: {created_count} created, {updated_count} updated[/green]")

    def _create_unit_courses(self, timetable_data):
        """Create unit-course relationships."""
        console.print("[cyan]Creating Unit-Course Relationships...[/cyan]")
        
        created_count = 0
        existing_count = 0
        
        with Progress() as progress:
            task = progress.add_task("Creating relationships...", total=len(timetable_data))
            
            for subject_code, subject_description, faculty in timetable_data:
                # Extract unit code
                unit_code_match = re.match(r'^([A-Z]+\d+)', subject_code)
                if not unit_code_match:
                    continue
                    
                unit_code = unit_code_match.group(1)
                
                # Determine course code and campus
                if 'H' in subject_code:
                    campus_code = 'H'
                    campus_name = 'SB'
                elif 'L' in subject_code:
                    campus_code = 'L'
                    campus_name = 'IR'
                else:
                    campus_code = 'O'
                    campus_name = 'ONLINE'
                
                # Determine course level
                unit_number = int(unit_code[3:])
                if 100 <= unit_number <= 199:
                    course_code = "BIT"
                elif 200 <= unit_number <= 399:
                    course_code = "BIT"
                elif 500 <= unit_number <= 599:
                    course_code = "GC-ICT"
                elif 700 <= unit_number <= 799:
                    course_code = "MIT"
                else:
                    course_code = "BIT"
                
                full_course_code = f"{course_code}-{campus_code}"
                
                # Determine year and term
                year = 2025  # Current year
                if 'SEM2' in subject_code:
                    term = 'Semester 2'
                elif 'SPR' in subject_code:
                    term = 'Spring'
                else:
                    term = 'Semester 1'
                
                try:
                    unit = Unit.objects.get(unit_code=unit_code)
                    course = Course.objects.get(course_code=full_course_code)
                    campus = Campus.objects.get(campus_name=campus_name) if campus_name != 'ONLINE' else None
                    
                    unit_course, created = UnitCourse.objects.get_or_create(
                        unit=unit,
                        course=course,
                        year=year,
                        term=term,
                        defaults={
                            'campus': campus,
                            'status': 'Active'
                        }
                    )
                    
                    if created:
                        created_count += 1
                        console.print(f"[green]✓[/green] Linked: {unit_code} ↔ {full_course_code} ({term} {year})")
                    else:
                        existing_count += 1
                
                except (Unit.DoesNotExist, Course.DoesNotExist, Campus.DoesNotExist) as e:
                    console.print(f"[red]Error creating relationship for {unit_code}: {str(e)}[/red]")
                
                progress.advance(task)
        
        console.print(f"[green]Unit-Course Relationships: {created_count} created, {existing_count} already existed[/green]")

    def _display_preview(self, units_data, courses_data):
        """Display preview of what would be created."""
        console.print("[cyan]PREVIEW MODE - What would be created:[/cyan]")
        
        # Units table
        units_table = Table(title="Units to be Created/Updated")
        units_table.add_column("Unit Code", style="cyan")
        units_table.add_column("Unit Name", style="green")
        units_table.add_column("Credits", style="yellow")
        
        for unit_code, unit_name in sorted(units_data.items()):
            units_table.add_row(unit_code, unit_name, "12.5")
        
        console.print(units_table)
        
        # Courses table
        courses_table = Table(title="Courses to be Created/Updated")
        courses_table.add_column("Course Code", style="cyan")
        courses_table.add_column("Course Name", style="green")
        courses_table.add_column("Campus", style="yellow")
        
        for course_code, course_info in sorted(courses_data.items()):
            courses_table.add_row(course_code, course_info['name'], course_info['campus'])
        
        console.print(courses_table)
        
        console.print(f"\n[yellow]Total: {len(units_data)} units and {len(courses_data)} courses would be processed[/yellow]")
        console.print("[cyan]Run without --dry-run to apply changes[/cyan]")
