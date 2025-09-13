from django.core.management.base import BaseCommand
from django.db import transaction
from units.models import Skill
from rich.console import Console
from rich.table import Table

console = Console()


class Command(BaseCommand):
    help = 'Seed skills data for ICT/IT units'

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
        
        # Refined and organized skills data
        skills_data = {
            # Programming Languages
            'Python': 'Python programming language fundamentals and advanced concepts',
            'Java': 'Java programming language and object-oriented programming',
            'JavaScript': 'JavaScript programming for web development',
            'Go-lang': 'Go programming language for system programming',
            'PHP': 'PHP server-side scripting language',
            'SQL': 'Structured Query Language for database operations',
            
            # Programming Concepts
            'Problem-solving': 'Analytical problem-solving and critical thinking skills',
            'Think Algorithmically': 'Algorithmic thinking and computational reasoning',
            'Control Structures': 'Programming control flow and logic structures',
            'Data Structures': 'Custom data structures and algorithms implementation',
            'Variables': 'Variable declaration, scope, and data manipulation',
            'Expressions': 'Programming expressions and operator usage',
            'Functions': 'Function design, implementation, and modular programming',
            'Understanding Code': 'Code comprehension and analysis skills',
            'Data Types': 'Programming data types and type systems',
            
            # Database & Data Management
            'Data Management': 'Database design, implementation, and administration',
            'SQL Queries': 'Advanced SQL query writing and optimization',
            'Writing Optimized Queries': 'Database query optimization and performance tuning',
            'Normalisation': 'Database normalization and schema design',
            'MongoDB': 'NoSQL database management with MongoDB',
            'Data Analysis': 'Statistical analysis and data interpretation',
            'Data Engineering': 'Data pipeline design and ETL processes',
            'Find Correlations': 'Statistical correlation analysis and pattern recognition',
            'Visualization Tools': 'Data visualization and reporting tools',
            
            # Machine Learning & AI
            'Machine Learning': 'Machine learning algorithms and model development',
            'Natural Language Processing': 'NLP techniques and text analysis',
            'Generative AI': 'Generative artificial intelligence and large language models',
            'Decision Trees': 'Decision tree algorithms and classification',
            'Logistic Regression': 'Logistic regression modeling and analysis',
            'K-nn': 'K-nearest neighbors algorithm implementation',
            
            # Cybersecurity
            'Cybersecurity Landscape': 'Understanding of current cybersecurity threats and trends',
            'CIA Triad': 'Confidentiality, Integrity, and Availability security principles',
            'Attack Models': 'Cybersecurity attack vectors and threat modeling',
            'Diagnose Security Issues': 'Security vulnerability assessment and analysis',
            'Digital Forensics': 'Digital evidence collection and forensic analysis',
            'Threats': 'Threat identification and risk assessment',
            'Detecting Errors': 'Error detection and security incident response',
            'Registry Viewer': 'Windows registry analysis for forensic investigations',
            'Sleuth Kit': 'Digital forensics toolkit usage and file system analysis',
            'Autopsy': 'Digital forensics platform for evidence analysis',
            'Wireshark': 'Network protocol analysis and packet inspection',
            
            # System Administration
            'System Administration': 'Server and system configuration management',
            'Network Administration': 'Network infrastructure management and configuration',
            'Desktop Support': 'End-user technical support and troubleshooting',
            'Linux': 'Linux operating system administration and command line',
            'MacOS': 'macOS system administration and support',
            'Network Stacks': 'Understanding of network protocol stacks',
            'Network Structures': 'Network topology and infrastructure design',
            'System Architecture': 'System design and architectural planning',
            'System Development': 'System development lifecycle and methodologies',
            'System Implementation Knowledge': 'System deployment and implementation strategies',
            
            # Software Development & Testing
            'Software Testing': 'Software testing methodologies and quality assurance',
            'Integration Testing': 'Integration testing strategies and implementation',
            'System Testing': 'End-to-end system testing and validation',
            'Fix Them': 'Bug fixing and software maintenance skills',
            
            # Research & Analysis
            'ICT Research Principles': 'Information technology research methodologies',
            'Literature Reviews': 'Academic literature review and analysis',
            'Quantitative Research Methods': 'Statistical research design and analysis',
            'Rigor': 'Academic and professional rigor in methodology',
            
            # Business & Communication
            'Communication': 'Professional communication and documentation',
            'Strong Communication Skills': 'Advanced verbal and written communication',
            'Improve Business Operations': 'Business process analysis and optimization',
            'Improve Efficiency': 'Process improvement and efficiency optimization',
            'Produce Actionable Results': 'Results-oriented analysis and reporting',
            'Build Valuable Experience': 'Professional development and skill building',
            
            # Teaching & Learning
            'Teaching Techniques': 'Educational methodology and instruction',
            'Confidence Students': 'Building student confidence and engagement',
            'Engaging': 'Student engagement and interactive learning',
            'Hands-on Experience': 'Practical, experiential learning approaches',
            'Curious Mind': 'Fostering curiosity and lifelong learning',
            'Confidence': 'Professional confidence and self-assurance',
            'Connections': 'Making conceptual connections and networking',
            'Continuous Development': 'Ongoing professional development and learning',
            
            # Specialized Tools & Technologies
            'Apex': 'Salesforce Apex programming and development',
            'Assess': 'Assessment and evaluation methodologies',
            'Assessments': 'Educational and professional assessment design',
            'When Properly Designed': 'Design thinking and best practices implementation',
        }

        console.print(f"[green]Found {len(skills_data)} skills to process[/green]")
        
        if not dry_run:
            with transaction.atomic():
                self._create_skills(skills_data)
        else:
            self._display_preview(skills_data)

    def _create_skills(self, skills_data):
        """Create skill records."""
        console.print("[cyan]Creating Skills...[/cyan]")
        
        created_count = 0
        updated_count = 0
        
        for skill_name, skill_description in skills_data.items():
            skill, created = Skill.objects.get_or_create(
                skill_name=skill_name,
                defaults={
                    'description': skill_description
                }
            )
            
            if created:
                created_count += 1
                console.print(f"[green]✓[/green] Created skill: {skill_name}")
            else:
                # Update description if different
                if skill.description != skill_description:
                    skill.description = skill_description
                    skill.save()
                    updated_count += 1
                    console.print(f"[yellow]↻[/yellow] Updated skill: {skill_name}")
        
        console.print(f"[green]Skills: {created_count} created, {updated_count} updated[/green]")

    def _display_preview(self, skills_data):
        """Display preview of what would be created."""
        console.print("[cyan]PREVIEW MODE - Skills to be created:[/cyan]")
        
        # Group skills by category for better display
        categories = {
            'Programming Languages': ['Python', 'Java', 'JavaScript', 'Go-lang', 'PHP', 'SQL'],
            'Programming Concepts': ['Problem-solving', 'Think Algorithmically', 'Control Structures', 
                                   'Data Structures', 'Variables', 'Expressions', 'Functions', 
                                   'Understanding Code', 'Data Types'],
            'Database & Data': ['Data Management', 'SQL Queries', 'Writing Optimized Queries', 
                              'Normalisation', 'MongoDB', 'Data Analysis', 'Data Engineering',
                              'Find Correlations', 'Visualization Tools'],
            'Machine Learning & AI': ['Machine Learning', 'Natural Language Processing', 'Generative AI',
                                    'Decision Trees', 'Logistic Regression', 'K-nn'],
            'Cybersecurity': ['Cybersecurity Landscape', 'CIA Triad', 'Attack Models', 
                            'Diagnose Security Issues', 'Digital Forensics', 'Threats',
                            'Detecting Errors', 'Registry Viewer', 'Sleuth Kit', 'Autopsy', 'Wireshark'],
            'System Administration': ['System Administration', 'Network Administration', 'Desktop Support',
                                    'Linux', 'MacOS', 'Network Stacks', 'Network Structures',
                                    'System Architecture', 'System Development', 'System Implementation Knowledge'],
            'Software Testing': ['Software Testing', 'Integration Testing', 'System Testing', 'Fix Them'],
            'Research & Analysis': ['ICT Research Principles', 'Literature Reviews', 
                                  'Quantitative Research Methods', 'Rigor'],
            'Business & Communication': ['Communication', 'Strong Communication Skills', 
                                       'Improve Business Operations', 'Improve Efficiency',
                                       'Produce Actionable Results', 'Build Valuable Experience'],
            'Teaching & Learning': ['Teaching Techniques', 'Confidence Students', 'Engaging',
                                  'Hands-on Experience', 'Curious Mind', 'Confidence',
                                  'Connections', 'Continuous Development'],
            'Specialized Tools': ['Apex', 'Assess', 'Assessments', 'When Properly Designed']
        }
        
        for category, skill_names in categories.items():
            if any(skill in skills_data for skill in skill_names):
                skills_table = Table(title=f"{category} Skills")
                skills_table.add_column("Skill Name", style="cyan")
                skills_table.add_column("Description", style="green")
                
                for skill_name in skill_names:
                    if skill_name in skills_data:
                        description = skills_data[skill_name]
                        # Truncate long descriptions for display
                        if len(description) > 60:
                            description = description[:57] + "..."
                        skills_table.add_row(skill_name, description)
                
                console.print(skills_table)
                console.print()
        
        console.print(f"[yellow]Total: {len(skills_data)} skills would be processed[/yellow]")
        console.print("[cyan]Run without --dry-run to apply changes[/cyan]")
