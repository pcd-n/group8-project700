from django.contrib import admin
from django.utils.html import format_html
from .models import EoiApp, MasterEoI, TutorsCourses, TutorSkills, TutorSupervisors


@admin.register(EoiApp)
class EoiAppAdmin(admin.ModelAdmin):
    """Admin for EoiApp model with SCD Type II support."""
    list_display = [
        'eoi_app_id', 'get_applicant_name', 'get_unit_info', 'status', 
        'is_current', 'version', 'valid_from', 'created_at'
    ]
    list_filter = ['status', 'is_current', 'valid_from', 'created_at', 'campus']
    search_fields = [
        'eoi_app_id', 'applicant_user__email', 'applicant_user__first_name',
        'applicant_user__last_name', 'unit__unit_code', 'unit__unit_name'
    ]
    readonly_fields = [
        'scd_id', 'eoi_app_id', 'valid_from', 'valid_to', 'is_current', 
        'version', 'created_at', 'updated_at'
    ]
    ordering = ['-created_at', '-version']
    
    fieldsets = (
        ('Application Details', {
            'fields': ('applicant_user', 'unit', 'campus', 'status', 'remarks')
        }),
        ('SCD Type II Controls', {
            'fields': ('eoi_app_id', 'is_current', 'version', 'valid_from', 'valid_to'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('scd_id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_applicant_name(self, obj):
        """Get applicant full name and email."""
        return f"{obj.applicant_user.get_full_name()} ({obj.applicant_user.email})"
    get_applicant_name.short_description = 'Applicant'
    
    def get_unit_info(self, obj):
        """Get unit code and name."""
        if obj.unit:
            return f"{obj.unit.unit_code} - {obj.unit.unit_name}"
        return "No unit specified"
    get_unit_info.short_description = 'Unit'
    
    def get_queryset(self, request):
        """Optimize queries."""
        return super().get_queryset(request).select_related(
            'applicant_user', 'unit', 'campus'
        )


@admin.register(MasterEoI)
class MasterEoIAdmin(admin.ModelAdmin):
    """Admin for MasterEoI model with SCD Type II support."""
    list_display = [
        'master_eoi_id', 'get_owner_name', 'get_course_info', 'intake_term',
        'status', 'is_current', 'version', 'created_at'
    ]
    list_filter = ['status', 'is_current', 'intake_term', 'created_at', 'campus']
    search_fields = [
        'master_eoi_id', 'owner_user__email', 'owner_user__first_name',
        'owner_user__last_name', 'course__course_code', 'course__course_name'
    ]
    readonly_fields = [
        'scd_id', 'master_eoi_id', 'valid_from', 'valid_to', 'is_current',
        'version', 'created_at', 'updated_at'
    ]
    ordering = ['-created_at', '-version']
    
    fieldsets = (
        ('EOI Campaign Details', {
            'fields': ('owner_user', 'course', 'campus', 'intake_term', 'status', 'notes')
        }),
        ('SCD Type II Controls', {
            'fields': ('master_eoi_id', 'is_current', 'version', 'valid_from', 'valid_to'),
            'classes': ('collapse',)
        }),
        ('Audit Information', {
            'fields': ('scd_id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_owner_name(self, obj):
        """Get owner full name and email."""
        return f"{obj.owner_user.get_full_name()} ({obj.owner_user.email})"
    get_owner_name.short_description = 'Owner'
    
    def get_course_info(self, obj):
        """Get course code and name."""
        if obj.course:
            return f"{obj.course.course_code} - {obj.course.course_name}"
        return "No course specified"
    get_course_info.short_description = 'Course'
    
    def get_queryset(self, request):
        """Optimize queries."""
        return super().get_queryset(request).select_related(
            'owner_user', 'course', 'campus'
        )


@admin.register(TutorsCourses)
class TutorsCoursesAdmin(admin.ModelAdmin):
    """Admin for TutorsCourses model."""
    list_display = ['get_tutor_name', 'get_course_info', 'assigned_at']
    list_filter = ['assigned_at', 'course']
    search_fields = [
        'tutor_user__email', 'tutor_user__first_name', 'tutor_user__last_name',
        'course__course_code', 'course__course_name'
    ]
    readonly_fields = ['assigned_at']
    ordering = ['-assigned_at']
    
    fieldsets = (
        ('Assignment', {
            'fields': ('tutor_user', 'course')
        }),
        ('Audit Information', {
            'fields': ('assigned_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_tutor_name(self, obj):
        """Get tutor full name and email."""
        return f"{obj.tutor_user.get_full_name()} ({obj.tutor_user.email})"
    get_tutor_name.short_description = 'Tutor'
    
    def get_course_info(self, obj):
        """Get course code and name."""
        return f"{obj.course.course_code} - {obj.course.course_name}"
    get_course_info.short_description = 'Course'
    
    def get_queryset(self, request):
        """Optimize queries."""
        return super().get_queryset(request).select_related(
            'tutor_user', 'course'
        )


@admin.register(TutorSkills)
class TutorSkillsAdmin(admin.ModelAdmin):
    """Admin for TutorSkills model."""
    list_display = [
        'get_tutor_name', 'get_skill_name', 'level', 'get_verification_status',
        'verified_at', 'created_at'
    ]
    list_filter = ['level', 'verified_at', 'created_at', 'skill']
    search_fields = [
        'tutor_user__email', 'tutor_user__first_name', 'tutor_user__last_name',
        'skill__skill_name', 'verified_by__email'
    ]
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Skill Assignment', {
            'fields': ('tutor_user', 'skill', 'level')
        }),
        ('Verification', {
            'fields': ('verified_by', 'verified_at')
        }),
        ('Audit Information', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_tutor_name(self, obj):
        """Get tutor full name and email."""
        return f"{obj.tutor_user.get_full_name()} ({obj.tutor_user.email})"
    get_tutor_name.short_description = 'Tutor'
    
    def get_skill_name(self, obj):
        """Get skill name."""
        return obj.skill.skill_name
    get_skill_name.short_description = 'Skill'
    
    def get_verification_status(self, obj):
        """Get verification status with color coding."""
        if obj.verified_at:
            verifier = obj.verified_by.get_full_name() if obj.verified_by else "Unknown"
            return format_html(
                '<span style="color: green;">✓ Verified by {}</span>',
                verifier
            )
        return format_html('<span style="color: orange;">⏳ Not Verified</span>')
    get_verification_status.short_description = 'Verification Status'
    
    def get_queryset(self, request):
        """Optimize queries."""
        return super().get_queryset(request).select_related(
            'tutor_user', 'skill', 'verified_by'
        )


@admin.register(TutorSupervisors)
class TutorSupervisorsAdmin(admin.ModelAdmin):
    """Admin for TutorSupervisors model."""
    list_display = ['get_tutor_name', 'get_supervisor_info', 'assigned_at']
    list_filter = ['assigned_at', 'supervisor__campus']
    search_fields = [
        'tutor_user__email', 'tutor_user__first_name', 'tutor_user__last_name',
        'supervisor__user__email', 'supervisor__user__first_name', 'supervisor__user__last_name'
    ]
    readonly_fields = ['assigned_at']
    ordering = ['-assigned_at']
    
    fieldsets = (
        ('Supervision Assignment', {
            'fields': ('tutor_user', 'supervisor')
        }),
        ('Audit Information', {
            'fields': ('assigned_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_tutor_name(self, obj):
        """Get tutor full name and email."""
        return f"{obj.tutor_user.get_full_name()} ({obj.tutor_user.email})"
    get_tutor_name.short_description = 'Tutor'
    
    def get_supervisor_info(self, obj):
        """Get supervisor info with campus."""
        supervisor_name = obj.supervisor.user.get_full_name()
        supervisor_email = obj.supervisor.user.email
        campus = obj.supervisor.campus.campus_name if obj.supervisor.campus else "No campus"
        return f"{supervisor_name} ({supervisor_email}) - {campus}"
    get_supervisor_info.short_description = 'Supervisor'
    
    def get_queryset(self, request):
        """Optimize queries."""
        return super().get_queryset(request).select_related(
            'tutor_user', 'supervisor__user', 'supervisor__campus'
        )
    
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Customize foreign key fields."""
        if db_field.name == 'tutor_user':
            kwargs["queryset"] = kwargs.get("queryset", db_field.related_model.objects).filter(
                is_active=True
            ).order_by('email')
        elif db_field.name == 'supervisor':
            kwargs["queryset"] = kwargs.get("queryset", db_field.related_model.objects).select_related(
                'user', 'campus'
            ).order_by('user__email')
        
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
