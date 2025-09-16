from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator
import uuid

class EoiApp(models.Model):
    """
    Expression of Interest Application model with SCD Type II support.
    Tracks individual tutor applications for specific units.
    """
    
    STATUS_CHOICES = [
        ('Submitted', 'Submitted'),
        ('Reviewed', 'Reviewed'),
        ('Accepted', 'Accepted'),
        ('Rejected', 'Rejected'),
    ]
    
    # SCD Type II primary key
    scd_id = models.AutoField(primary_key=True)
    
    # Business key (stable across versions)
    eoi_app_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        help_text="Stable business identifier across versions"
    )
    
    # Core fields
    applicant_user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='eoi_applications',
        help_text="User applying for the tutoring position"
    )
    unit = models.ForeignKey(
        'units.Unit',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eoi_applications',
        help_text="Unit being applied for"
    )
    campus = models.ForeignKey(
        'users.Campus',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='eoi_applications',
        help_text="Campus where tutoring will take place"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Submitted',
        help_text="Current status of the application"
    )
    remarks = models.TextField(
        blank=True,
        help_text="Additional notes or comments about the application"
    )

    # Pham: added the 3 followings for 'allocation'
    preference = models.IntegerField(
        default=0,
        help_text="Coordinator-set priority (1 = highest, 2 = next, etc.)"
    )
    qualifications = models.TextField(
        blank=True,
        null=True,
        help_text="Tutor qualifications provided via EOI"
    )
    # --- Extra fields from EOI template ---
    tutor_email = models.EmailField(max_length=254, db_index=True, null=True, blank=True) # null temporarily accepted
    tutor_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Tutor full name from EOI form"
    )
    tutor_current = models.CharField(
        max_length=100,
        blank=True,
        help_text="Raw text from 'You are' (EOI)"
    )
    location_text = models.CharField(
        max_length=100,
        blank=True,
        help_text="Raw campus/location text from EOI"
    )
    gpa = models.DecimalField(
        max_digits=4, decimal_places=2, null=True, blank=True,
        help_text="GPA as per EOI"
    )
    supervisor = models.CharField(
        max_length=255,
        blank=True,
        help_text="Supervisor / references"
    )
    applied_units = models.JSONField(
        null=True, blank=True,
        help_text="Array of applied unit codes from EOI"
    )
    tutoring_experience = models.TextField(
        blank=True,
        help_text="Tutoring experience listed in EOI"
    )
    hours_available = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Total tutoring hours available"
    )
    scholarship_received = models.BooleanField(
        null=True, blank=True,
        help_text="Scholarship received (PhD only)"
    )
    transcript_link = models.URLField(
        max_length=500, blank=True,
        help_text="Transcript link"
    )
    cv_link = models.URLField(
        max_length=500, blank=True,
        help_text="CV link"
    )

    # Existing
    availability = models.TextField(
        blank=True,
        null=True,
        help_text="Tutor availability provided via EOI"
    )

    # SCD Type II control fields
    valid_from = models.DateTimeField(
        default=timezone.now,
        help_text="Start of validity period (inclusive)"
    )
    valid_to = models.DateTimeField(
        null=True,
        blank=True,
        help_text="End of validity period (exclusive); null when current"
    )
    is_current = models.BooleanField(
        default=True,
        help_text="True if this is the current version"
    )
    version = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Version number of this record"
    )
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'eoi_app'
        ordering = ['-created_at', '-version']
        verbose_name = 'EOI Application'
        verbose_name_plural = 'EOI Applications'
        
        indexes = [
            models.Index(fields=['eoi_app_id', 'is_current']),
            models.Index(fields=['eoi_app_id', 'valid_from']),
            models.Index(fields=['status']),
            models.Index(fields=['valid_from', 'valid_to']),
        ]
    
    def __str__(self):
        unit_str = f" for {self.unit.unit_code}" if self.unit else ""
        return f"EOI Application by {self.applicant_user.email}{unit_str} (v{self.version})"
    
    def save(self, *args, **kwargs):
        """Override save to handle SCD Type II logic."""
        if self.pk is None:  # New record
            # Check if there's an existing current record with same business key
            existing = EoiApp.objects.filter(
                eoi_app_id=self.eoi_app_id,
                is_current=True
            ).first()
            
            if existing:
                # Close the existing record
                existing.is_current = False
                existing.valid_to = timezone.now()
                existing.save()
                
                # Set new version number
                self.version = existing.version + 1
        
        super().save(*args, **kwargs)


class MasterEoI(models.Model):
    """
    Master Expression of Interest model with SCD Type II support.
    Represents EOI campaigns for specific courses/units.
    """
    
    STATUS_CHOICES = [
        ('Planned', 'Planned'),
        ('Open', 'Open'),
        ('Closed', 'Closed'),
        ('Archived', 'Archived'),
    ]
    
    # SCD Type II primary key
    scd_id = models.AutoField(primary_key=True)
    
    # Business key (stable across versions)
    master_eoi_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        help_text="Stable business identifier across versions"
    )
    
    # Core fields
    owner_user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='owned_master_eois',
        help_text="User who owns/manages this EOI campaign"
    )
    course = models.ForeignKey(
        'units.Course',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='master_eois',
        help_text="Course this EOI campaign is for"
    )
    campus = models.ForeignKey(
        'users.Campus',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='master_eois',
        help_text="Campus for this EOI campaign"
    )
    intake_term = models.CharField(
        max_length=20,
        blank=True,
        help_text="Academic term (e.g., 2025S1, 2025S2)"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='Planned',
        help_text="Current status of the EOI campaign"
    )
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this EOI campaign"
    )
    
    # SCD Type II control fields
    valid_from = models.DateTimeField(
        default=timezone.now,
        help_text="Start of validity period (inclusive)"
    )
    valid_to = models.DateTimeField(
        null=True,
        blank=True,
        help_text="End of validity period (exclusive); null when current"
    )
    is_current = models.BooleanField(
        default=True,
        help_text="True if this is the current version"
    )
    version = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Version number of this record"
    )
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'master_eoi'
        ordering = ['-created_at', '-version']
        verbose_name = 'Master EOI'
        verbose_name_plural = 'Master EOIs'
        
        indexes = [
            models.Index(fields=['master_eoi_id', 'is_current']),
            models.Index(fields=['master_eoi_id', 'valid_from']),
            models.Index(fields=['status']),
            models.Index(fields=['intake_term']),
        ]
    
    def __str__(self):
        course_str = f" for {self.course.course_code}" if self.course else ""
        term_str = f" ({self.intake_term})" if self.intake_term else ""
        return f"Master EOI{course_str}{term_str} (v{self.version})"
    
    def save(self, *args, **kwargs):
        """Override save to handle SCD Type II logic."""
        if self.pk is None:  # New record
            # Check if there's an existing current record with same business key
            existing = MasterEoI.objects.filter(
                master_eoi_id=self.master_eoi_id,
                is_current=True
            ).first()
            
            if existing:
                # Close the existing record
                existing.is_current = False
                existing.valid_to = timezone.now()
                existing.save()
                
                # Set new version number
                self.version = existing.version + 1
        
        super().save(*args, **kwargs)


class TutorsCourses(models.Model):
    """
    Many-to-many relationship between tutors and courses they're assigned to.
    """
    tutor_user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='tutor_courses',
        help_text="Tutor user"
    )
    course = models.ForeignKey(
        'units.Course',
        on_delete=models.CASCADE,
        related_name='course_tutors',
        help_text="Course the tutor is assigned to"
    )
    assigned_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the tutor was assigned to this course"
    )
    
    class Meta:
        db_table = 'tutors_courses'
        unique_together = ['tutor_user', 'course']
        ordering = ['-assigned_at']
        verbose_name = 'Tutor Course Assignment'
        verbose_name_plural = 'Tutor Course Assignments'
        
        indexes = [
            models.Index(fields=['tutor_user', 'course']),
            models.Index(fields=['assigned_at']),
        ]
    
    def __str__(self):
        return f"{self.tutor_user.email} → {self.course.course_code}"


class TutorSkills(models.Model):
    """
    Skills possessed by tutors with verification support.
    """
    
    LEVEL_CHOICES = [
        ('Beginner', 'Beginner'),
        ('Intermediate', 'Intermediate'),
        ('Advanced', 'Advanced'),
        ('Expert', 'Expert'),
    ]
    
    tutor_user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='tutor_skills',
        help_text="Tutor user"
    )
    skill = models.ForeignKey(
        'units.Skill',
        on_delete=models.CASCADE,
        related_name='skill_tutors',
        help_text="Skill possessed by the tutor"
    )
    level = models.CharField(
        max_length=20,
        choices=LEVEL_CHOICES,
        default='Intermediate',
        help_text="Proficiency level of the tutor in this skill"
    )
    verified_by = models.ForeignKey(
        'users.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_tutor_skills',
        help_text="User who verified this skill"
    )
    verified_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this skill was verified"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'tutor_skills'
        unique_together = ['tutor_user', 'skill']
        ordering = ['tutor_user__email', 'skill__skill_name']
        verbose_name = 'Tutor Skill'
        verbose_name_plural = 'Tutor Skills'
        
        indexes = [
            models.Index(fields=['tutor_user', 'skill']),
            models.Index(fields=['level']),
            models.Index(fields=['verified_at']),
        ]
    
    def __str__(self):
        verified_str = " (verified)" if self.verified_at else ""
        return f"{self.tutor_user.email} - {self.skill.skill_name} ({self.level}){verified_str}"


class TutorSupervisors(models.Model):
    """
    Relationship between tutors and their supervisors.
    """
    tutor_user = models.ForeignKey(
        'users.User',
        on_delete=models.CASCADE,
        related_name='tutor_supervisors',
        help_text="Tutor user"
    )
    supervisor = models.ForeignKey(
        'users.Supervisor',
        on_delete=models.CASCADE,
        related_name='supervised_tutors',
        help_text="Supervisor assigned to this tutor"
    )
    assigned_at = models.DateTimeField(
        auto_now_add=True,
        help_text="When the supervisor was assigned to this tutor"
    )
    
    class Meta:
        db_table = 'tutor_supervisors'
        unique_together = ['tutor_user', 'supervisor']
        ordering = ['-assigned_at']
        verbose_name = 'Tutor Supervisor Assignment'
        verbose_name_plural = 'Tutor Supervisor Assignments'
        
        indexes = [
            models.Index(fields=['tutor_user', 'supervisor']),
            models.Index(fields=['assigned_at']),
        ]
    
    def __str__(self):
        return f"{self.tutor_user.email} supervised by {self.supervisor.user.email}"
