#units/models.py
from django.db import models
from django.core.validators import MinValueValidator
from users.models import Campus


class Unit(models.Model):
    """
    Model representing a university unit/subject.
    """
    unit_id = models.AutoField(primary_key=True)
    unit_code = models.CharField(
        max_length=20, 
        unique=True, 
        help_text="Unique unit code (e.g., MATH101)"
    )
    unit_name = models.CharField(
        max_length=255, 
        help_text="Full name of the unit"
    )
    credits = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        null=True,
        blank=True,
        help_text="Credit points for the unit (may be null if unknown)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'units'
        ordering = ['unit_code']
        verbose_name = 'Unit'
        verbose_name_plural = 'Units'

    def __str__(self):
        return f"{self.unit_code} - {self.unit_name}"

    def clean(self):
        """Validate unit data."""
        if self.unit_code:
            self.unit_code = self.unit_code.upper().strip()


class Course(models.Model):
    """
    Model representing a degree course/program.
    """
    course_id = models.AutoField(primary_key=True)
    course_code = models.CharField(
        max_length=20, 
        unique=True, 
        help_text="Unique course code (e.g., BSC-DS)"
    )
    course_name = models.CharField(
        max_length=255, 
        help_text="Full name of the course"
    )
    campus = models.ForeignKey(
        Campus,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='primary_courses',
        help_text="Primary campus for this course (optional)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'courses'
        ordering = ['course_code']
        verbose_name = 'Course'
        verbose_name_plural = 'Courses'

    def __str__(self):
        return f"{self.course_code} - {self.course_name}"

    def clean(self):
        """Validate course data."""
        if self.course_code:
            self.course_code = self.course_code.upper().strip()


class UnitCourse(models.Model):
    """
    Model representing the relationship between units and courses,
    including delivery campus, term, and year information.
    """
    
    STATUS_CHOICES = [
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ]
    
    unit_course_id = models.AutoField(primary_key=True)
    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name='unit_courses',
        help_text="The unit being offered"
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name='course_units',
        help_text="The course this unit belongs to"
    )
    campus = models.ForeignKey(
        Campus,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='unit_offerings',
        help_text="Campus where this unit is delivered (optional)"
    )
    term = models.CharField(
        max_length=20,
        blank=True,
        help_text="Academic term (e.g., 2025S1, 2025S2)"
    )
    year = models.PositiveIntegerField(
        validators=[MinValueValidator(2020)],
        null=True,
        blank=True,
        help_text="Academic year"
    )
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default='Active',
        help_text="Current status of this unit-course relationship"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'unit_courses'
        ordering = ['year', 'term', 'unit__unit_code']
        verbose_name = 'Unit Course'
        verbose_name_plural = 'Unit Courses'
        
        # Unique constraint to prevent duplicate unit-course-term-year-campus combinations
        constraints = [
            models.UniqueConstraint(
                fields=['unit', 'course', 'term', 'year', 'campus'],
                name='unique_unit_course_term_year_campus'
            )
        ]
        
        # Database indexes for better query performance
        indexes = [
            models.Index(fields=['unit']),
            models.Index(fields=['course']),
            models.Index(fields=['year', 'term']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        campus_str = f" at {self.campus.campus_name}" if self.campus else ""
        term_str = f" ({self.term})" if self.term else ""
        return f"{self.unit.unit_code} in {self.course.course_code}{campus_str}{term_str}"

    def clean(self):
        """Validate unit course data."""
        if self.term:
            self.term = self.term.upper().strip()


class Skill(models.Model):
    """
    Model representing skills that can be associated with units, users, or other entities.
    """
    skill_id = models.AutoField(primary_key=True)
    skill_name = models.CharField(
        max_length=100, 
        unique=True,
        help_text="Unique name of the skill"
    )
    description = models.TextField(
        blank=True,
        help_text="Detailed description of the skill"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'skills'
        ordering = ['skill_name']
        verbose_name = 'Skill'
        verbose_name_plural = 'Skills'

    def __str__(self):
        return self.skill_name

    def clean(self):
        """Validate skill data."""
        if self.skill_name:
            self.skill_name = self.skill_name.strip()


# Optional: Many-to-many relationship between Units and Skills
class UnitSkill(models.Model):
    """
    Model representing the relationship between units and required/taught skills.
    """
    unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name='unit_skills'
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.CASCADE,
        related_name='skill_units'
    )
    proficiency_level = models.CharField(
        max_length=20,
        choices=[
            ('Beginner', 'Beginner'),
            ('Intermediate', 'Intermediate'),
            ('Advanced', 'Advanced'),
            ('Expert', 'Expert'),
        ],
        default='Intermediate',
        help_text="Required or taught proficiency level"
    )
    is_required = models.BooleanField(
        default=False,
        help_text="Whether this skill is required for the unit"
    )
    is_taught = models.BooleanField(
        default=True,
        help_text="Whether this skill is taught in the unit"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'unit_skills'
        unique_together = ['unit', 'skill']
        ordering = ['unit__unit_code', 'skill__skill_name']
        verbose_name = 'Unit Skill'
        verbose_name_plural = 'Unit Skills'

    def __str__(self):
        return f"{self.unit.unit_code} - {self.skill.skill_name} ({self.proficiency_level})"
