#timetable/models.py
from django.db import models
from django.utils import timezone
from units.models import UnitCourse
from users.models import User, Campus
import uuid


class MasterClassTime(models.Model):
    """
    Master class schedule that holds all course schedule information.
    This represents the complete class schedule imported from CSV files.
    """
    
    # Primary key
    master_class_id = models.AutoField(primary_key=True)
    
    # Subject and course information
    subject_code = models.CharField(
        max_length=50,
        help_text="Subject code (e.g., KIT101_H_SEM2_I)"
    )
    subject_description = models.CharField(
        max_length=255,
        help_text="Subject description (e.g., Programming Fundamentals)"
    )
    faculty = models.CharField(
        max_length=50,
        help_text="Faculty code (e.g., SAA-313)"
    )
    
    # Activity information
    activity_group_code = models.CharField(
        max_length=50,
        help_text="Activity group code (e.g., Tut-A, Lec-A, Wks-A)"
    )
    activity_code = models.CharField(
        max_length=50,
        help_text="Specific activity code (e.g., TutA-01, LecA-01)"
    )
    activity_description = models.CharField(
        max_length=255,
        blank=True,
        help_text="Activity description"
    )
    
    # Campus and location
    campus = models.CharField(
        max_length=20,
        help_text="Campus code (SB, IR, Online)"
    )
    location = models.CharField(
        max_length=100,
        blank=True,
        help_text="Room/location code (e.g., SB.AR15L02275)"
    )
    
    # Scheduling information
    day_of_week = models.CharField(
        max_length=20,
        help_text="Day of the week (Mon, Tue, Wed, etc.)"
    )
    start_time = models.TimeField(
        help_text="Start time of the class"
    )
    weeks = models.CharField(
        max_length=255,
        help_text="Week schedule pattern (e.g., '29/7-26/8, 9/9-21/10')"
    )
    teaching_weeks = models.PositiveIntegerField(
        help_text="Number of teaching weeks"
    )
    duration = models.PositiveIntegerField(
        help_text="Duration in minutes"
    )
    
    # Staff and capacity information
    staff = models.CharField(
        max_length=255,
        blank=True,
        help_text="Assigned staff member"
    )
    size = models.PositiveIntegerField(
        default=0,
        help_text="Class size/capacity"
    )
    buffer = models.IntegerField(
        default=0,
        help_text="Buffer capacity"
    )
    adjusted_size = models.PositiveIntegerField(
        default=0,
        help_text="Adjusted class size"
    )
    student_count = models.PositiveIntegerField(
        default=0,
        help_text="Current student count"
    )
    constraint_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of constraints"
    )
    
    # Grouping and classification
    cluster = models.CharField(
        max_length=50,
        blank=True,
        help_text="Class cluster"
    )
    group = models.CharField(
        max_length=50,
        blank=True,
        help_text="Class group"
    )
    notes = models.TextField(
        blank=True,
        default="",
        help_text="Free text notes for this timetable slot"
    )

    # Display and availability flags
    show_on_timetable = models.BooleanField(
        default=True,
        help_text="Whether to show on timetable (Y/N)"
    )
    available_for_allocation = models.BooleanField(
        default=True,
        help_text="Whether available for tutor allocation (Y/N)"
    )
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'master_class_time'
        ordering = ['subject_code', 'day_of_week', 'start_time']
        verbose_name = 'Master Class Time'
        verbose_name_plural = 'Master Class Times'
        
        indexes = [
            models.Index(fields=['subject_code']),
            models.Index(fields=['campus']),
            models.Index(fields=['day_of_week', 'start_time']),
            models.Index(fields=['available_for_allocation']),
            models.Index(fields=['activity_group_code']),
        ]
        
        constraints = [
            models.UniqueConstraint(
                fields=['subject_code', 'activity_code', 'campus'],
                name='unique_subject_activity_campus'
            )
        ]

    def __str__(self):
        return f"{self.subject_code} - {self.activity_code} - {self.campus} - {self.day_of_week} {self.start_time}"

    @property
    def end_time(self):
        """Calculate end time based on start time and duration."""
        from datetime import timedelta
        start_datetime = timezone.datetime.combine(timezone.datetime.today().date(), self.start_time)
        end_datetime = start_datetime + timedelta(minutes=self.duration)
        return end_datetime.time()

    @property
    def enrollment_percentage(self):
        """Calculate enrollment percentage."""
        if self.adjusted_size > 0:
            return (self.student_count / self.adjusted_size) * 100
        return 0

    @property
    def has_staff_assigned(self):
        """Check if staff is assigned."""
        return bool(self.staff and self.staff.strip() and self.staff != '-')


class TimeTable(models.Model):
    """
    Timetable model for tutor allocation and scheduling.
    This holds the actual tutor assignments after allocation.
    """
    
    DAY_CHOICES = [
        ('MON', 'Monday'),
        ('TUE', 'Tuesday'),
        ('WED', 'Wednesday'),
        ('THU', 'Thursday'),
        ('FRI', 'Friday'),
        ('SAT', 'Saturday'),
        ('SUN', 'Sunday'),
    ]
    
    # Primary key
    timetable_id = models.AutoField(primary_key=True)
    
    # Foreign key relationships
    unit_course = models.ForeignKey(
        UnitCourse,
        on_delete=models.CASCADE,
        related_name='timetables',
        help_text="Unit-Course combination"
    )
    campus = models.ForeignKey(
        Campus,
        on_delete=models.CASCADE,
        related_name='timetables',
        help_text="Campus where the class is held"
    )
    tutor_user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tutor_timetables',
        help_text="Assigned tutor"
    )
    
    # Optional reference to master class (for traceability)
    master_class = models.ForeignKey(
        MasterClassTime,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='timetable_allocations',
        help_text="Reference to master class schedule"
    )

    notes = models.TextField(
        blank=True,
        default="",
        help_text="Allocation notes for this session"
    )
    
    # Location and timing
    room = models.CharField(
        max_length=100,
        blank=True,
        help_text="Room/location identifier"
    )
    day_of_week = models.CharField(
        max_length=10,
        choices=DAY_CHOICES,
        help_text="Day of the week"
    )
    start_time = models.TimeField(
        help_text="Start time of the class"
    )
    end_time = models.TimeField(
        help_text="End time of the class"
    )
    
    # Date range (for semester/term scheduling)
    start_date = models.DateField(
        null=True,
        blank=True,
        help_text="Start date of the timetable period"
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        help_text="End date of the timetable period"
    )
    
    # Audit fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'timetable'
        ordering = ['unit_course__unit__unit_code', 'day_of_week', 'start_time']
        verbose_name = 'Timetable'
        verbose_name_plural = 'Timetables'
        
        indexes = [
            models.Index(fields=['unit_course']),
            models.Index(fields=['campus']),
            models.Index(fields=['tutor_user']),
            models.Index(fields=['day_of_week', 'start_time']),
            models.Index(fields=['start_date', 'end_date']),
        ]
        
        constraints = [
            models.UniqueConstraint(
                fields=['unit_course', 'campus', 'day_of_week', 'start_time'],
                name='unique_timetable_slot'
            )
        ]

    def __str__(self):
        unit_code = self.unit_course.unit.unit_code
        tutor_name = self.tutor_user.get_full_name() if self.tutor_user else "Unassigned"
        return f"{unit_code} - {self.campus.campus_name} - {self.day_of_week} {self.start_time} ({tutor_name})"

    @property
    def duration_minutes(self):
        """Calculate duration in minutes."""
        if self.start_time and self.end_time:
            start_datetime = timezone.datetime.combine(timezone.datetime.today().date(), self.start_time)
            end_datetime = timezone.datetime.combine(timezone.datetime.today().date(), self.end_time)
            return int((end_datetime - start_datetime).total_seconds() / 60)
        return 0

    @property
    def is_tutor_assigned(self):
        """Check if a tutor is assigned."""
        return self.tutor_user is not None

    def can_assign_tutor(self, tutor):
        """
        Check if a tutor can be assigned to this timetable slot.
        Validates against existing allocations and availability.
        """
        if self.tutor_user and self.tutor_user != tutor:
            return False, f"Already assigned to {self.tutor_user.get_full_name()}"
        
        # Check for conflicts with other timetable assignments
        conflicting_assignments = TimeTable.objects.filter(
            tutor_user=tutor,
            day_of_week=self.day_of_week,
            start_time__lt=self.end_time,
            end_time__gt=self.start_time
        ).exclude(pk=self.pk)
        
        if conflicting_assignments.exists():
            return False, "Tutor has conflicting assignment at this time"
        
        # Check if tutor has required skills for this unit
        from eoi.models import TutorSkills
        required_skills = self.unit_course.unit.unit_skills.filter(is_required=True)
        
        if required_skills.exists():
            tutor_skills = TutorSkills.objects.filter(
                tutor_user=tutor,
                skill__in=[us.skill for us in required_skills],
                verified_at__isnull=False
            )
            
            missing_skills = required_skills.exclude(
                skill__in=[ts.skill for ts in tutor_skills]
            )
            
            if missing_skills.exists():
                skill_names = [ms.skill.skill_name for ms in missing_skills]
                return False, f"Missing required skills: {', '.join(skill_names)}"
        
        return True, "Can be assigned"

    def assign_tutor(self, tutor, user=None):
        """Assign a tutor to this timetable slot with validation."""
        can_assign, message = self.can_assign_tutor(tutor)
        
        if not can_assign:
            raise ValueError(f"Cannot assign tutor: {message}")
        
        self.tutor_user = tutor
        self.save()
        
        # Create allocation record in EOI app if needed
        from eoi.models import TutorsCourses
        TutorsCourses.objects.get_or_create(
            tutor_user=tutor,
            course=self.unit_course.course
        )
        
        return True

    def unassign_tutor(self):
        """Remove tutor assignment from this timetable slot."""
        self.tutor_user = None
        self.save()


class TimetableImportLog(models.Model):
    """
    Model to track timetable imports from CSV files.
    Provides audit trail for data imports.
    """
    
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Processing', 'Processing'),
        ('Completed', 'Completed'),
        ('Failed', 'Failed'),
    ]
    
    import_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        help_text="Unique identifier for this import"
    )
    filename = models.CharField(
        max_length=255,
        help_text="Original filename of the imported CSV"
    )
    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='timetable_imports',
        help_text="User who uploaded the file"
    )
    status = models.CharField(
        max_length=50,
        choices=STATUS_CHOICES,
        default='Pending',
        help_text="Status of the import process"
    )
    total_rows = models.PositiveIntegerField(
        default=0,
        help_text="Total number of rows in the CSV"
    )
    processed_rows = models.PositiveIntegerField(
        default=0,
        help_text="Number of rows successfully processed"
    )
    error_rows = models.PositiveIntegerField(
        default=0,
        help_text="Number of rows with errors"
    )
    error_log = models.TextField(
        blank=True,
        help_text="Log of errors encountered during import"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the import was completed"
    )

    class Meta:
        db_table = 'timetable_import_logs'
        ordering = ['-created_at']
        verbose_name = 'Timetable Import Log'
        verbose_name_plural = 'Timetable Import Logs'

    def __str__(self):
        return f"Import {self.filename} by {self.uploaded_by.email} ({self.status})"

    @property
    def success_rate(self):
        """Calculate success rate of the import."""
        if self.total_rows > 0:
            return (self.processed_rows / self.total_rows) * 100
        return 0
