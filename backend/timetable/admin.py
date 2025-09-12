from django.contrib import admin
from django.utils.html import format_html
from .models import MasterClassTime, TimeTable, TimetableImportLog


@admin.register(MasterClassTime)
class MasterClassTimeAdmin(admin.ModelAdmin):
    list_display = [
        'subject_code', 'activity_code', 'campus', 'day_of_week', 
        'start_time', 'end_time', 'duration', 'staff_display',
        'enrollment_display', 'availability_status'
    ]
    list_filter = [
        'campus', 'day_of_week', 'activity_group_code', 
        'available_for_allocation', 'show_on_timetable', 'faculty'
    ]
    search_fields = [
        'subject_code', 'subject_description', 'activity_code', 
        'location', 'staff'
    ]
    ordering = ['subject_code', 'day_of_week', 'start_time']
    
    fieldsets = (
        ('Subject Information', {
            'fields': ('subject_code', 'subject_description', 'faculty')
        }),
        ('Activity Details', {
            'fields': ('activity_group_code', 'activity_code', 'activity_description')
        }),
        ('Scheduling', {
            'fields': ('campus', 'location', 'day_of_week', 'start_time', 'duration', 'weeks', 'teaching_weeks')
        }),
        ('Capacity & Enrollment', {
            'fields': ('size', 'buffer', 'adjusted_size', 'student_count', 'constraint_count')
        }),
        ('Staff & Grouping', {
            'fields': ('staff', 'cluster', 'group')
        }),
        ('Settings', {
            'fields': ('show_on_timetable', 'available_for_allocation')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def staff_display(self, obj):
        if obj.has_staff_assigned:
            return obj.staff
        return format_html('<span style="color: orange;">Not Assigned</span>')
    staff_display.short_description = 'Staff'
    staff_display.admin_order_field = 'staff'
    
    def enrollment_display(self, obj):
        if obj.adjusted_size > 0:
            percentage = obj.enrollment_percentage
            color = 'green' if percentage <= 80 else 'orange' if percentage <= 100 else 'red'
            return format_html(
                '<span style="color: {};">{}/{} ({:.0f}%)</span>',
                color, obj.student_count, obj.adjusted_size, percentage
            )
        return f"{obj.student_count}/0"
    enrollment_display.short_description = 'Enrollment'
    
    def availability_status(self, obj):
        if obj.available_for_allocation:
            return format_html('<span style="color: green;">✓ Available</span>')
        else:
            return format_html('<span style="color: red;">✗ Not Available</span>')
    availability_status.short_description = 'Allocation Status'
    availability_status.admin_order_field = 'available_for_allocation'
    
    actions = [
        'mark_available_for_allocation', 'mark_not_available_for_allocation',
        'show_on_timetable', 'hide_from_timetable'
    ]
    
    def mark_available_for_allocation(self, request, queryset):
        updated = queryset.update(available_for_allocation=True)
        self.message_user(request, f'{updated} classes marked as available for allocation.')
    mark_available_for_allocation.short_description = "Mark as available for allocation"
    
    def mark_not_available_for_allocation(self, request, queryset):
        updated = queryset.update(available_for_allocation=False)
        self.message_user(request, f'{updated} classes marked as not available for allocation.')
    mark_not_available_for_allocation.short_description = "Mark as not available for allocation"
    
    def show_on_timetable(self, request, queryset):
        updated = queryset.update(show_on_timetable=True)
        self.message_user(request, f'{updated} classes set to show on timetable.')
    show_on_timetable.short_description = "Show on timetable"
    
    def hide_from_timetable(self, request, queryset):
        updated = queryset.update(show_on_timetable=False)
        self.message_user(request, f'{updated} classes set to hide from timetable.')
    hide_from_timetable.short_description = "Hide from timetable"


@admin.register(TimeTable)
class TimeTableAdmin(admin.ModelAdmin):
    list_display = [
        'unit_display', 'campus_display', 'day_of_week', 
        'start_time', 'end_time', 'room', 'tutor_display', 
        'period_display', 'assignment_status'
    ]
    list_filter = [
        'campus', 'day_of_week', 'unit_course__unit__unit_code',
        'unit_course__course__course_name', 'start_date', 'end_date'
    ]
    search_fields = [
        'unit_course__unit__unit_code', 'unit_course__unit__unit_name',
        'unit_course__course__course_name', 'room', 'tutor_user__email',
        'tutor_user__first_name', 'tutor_user__last_name'
    ]
    ordering = ['unit_course__unit__unit_code', 'day_of_week', 'start_time']
    
    fieldsets = (
        ('Course & Location', {
            'fields': ('unit_course', 'campus', 'room')
        }),
        ('Scheduling', {
            'fields': ('day_of_week', 'start_time', 'end_time')
        }),
        ('Period', {
            'fields': ('start_date', 'end_date')
        }),
        ('Tutor Assignment', {
            'fields': ('tutor_user',)
        }),
        ('Master Class Reference', {
            'fields': ('master_class',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ('created_at', 'updated_at')
    
    def unit_display(self, obj):
        return f"{obj.unit_course.unit.unit_code}"
    unit_display.short_description = 'Unit'
    unit_display.admin_order_field = 'unit_course__unit__unit_code'
    
    def campus_display(self, obj):
        return obj.campus.campus_name
    campus_display.short_description = 'Campus'
    campus_display.admin_order_field = 'campus__campus_name'
    
    def tutor_display(self, obj):
        if obj.tutor_user:
            return obj.tutor_user.get_full_name() or obj.tutor_user.email
        return format_html('<span style="color: orange;">Unassigned</span>')
    tutor_display.short_description = 'Assigned Tutor'
    tutor_display.admin_order_field = 'tutor_user__email'
    
    def period_display(self, obj):
        if obj.start_date and obj.end_date:
            return f"{obj.start_date} to {obj.end_date}"
        elif obj.start_date:
            return f"From {obj.start_date}"
        elif obj.end_date:
            return f"Until {obj.end_date}"
        return "Not specified"
    period_display.short_description = 'Period'
    
    def assignment_status(self, obj):
        if obj.tutor_user:
            return format_html('<span style="color: green;">✓ Assigned</span>')
        else:
            return format_html('<span style="color: red;">⚠ Needs Assignment</span>')
    assignment_status.short_description = 'Status'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'unit_course', 'unit_course__unit', 'unit_course__course', 
            'campus', 'tutor_user', 'master_class'
        )
    
    actions = ['clear_tutor_assignments', 'assign_to_master_class']
    
    def clear_tutor_assignments(self, request, queryset):
        updated = queryset.update(tutor_user=None)
        self.message_user(request, f'Tutor assignments cleared for {updated} timetable entries.')
    clear_tutor_assignments.short_description = "Clear tutor assignments"
    
    def assign_to_master_class(self, request, queryset):
        """Attempt to link timetable entries to corresponding master class entries"""
        linked_count = 0
        for timetable in queryset:
            # Try to find matching master class
            master_classes = MasterClassTime.objects.filter(
                subject_code__contains=timetable.unit_course.unit.unit_code,
                campus=timetable.campus.campus_name,
                day_of_week__icontains=timetable.day_of_week[:3],  # Match first 3 letters
                start_time=timetable.start_time
            )
            if master_classes.exists():
                timetable.master_class = master_classes.first()
                timetable.save()
                linked_count += 1
        
        self.message_user(request, f'{linked_count} timetable entries linked to master classes.')
    assign_to_master_class.short_description = "Link to master class data"


@admin.register(TimetableImportLog)
class TimetableImportLogAdmin(admin.ModelAdmin):
    list_display = [
        'filename', 'uploaded_by', 'status', 'total_rows', 
        'processed_rows', 'error_rows', 'success_rate_display', 'created_at'
    ]
    list_filter = ['status', 'created_at', 'uploaded_by']
    search_fields = ['filename', 'uploaded_by__email']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Import Details', {
            'fields': ('filename', 'uploaded_by', 'status')
        }),
        ('Statistics', {
            'fields': ('total_rows', 'processed_rows', 'error_rows')
        }),
        ('Error Information', {
            'fields': ('error_log',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'completed_at')
        }),
    )
    
    readonly_fields = ('import_id', 'created_at', 'completed_at')
    
    def success_rate_display(self, obj):
        rate = obj.success_rate
        if rate >= 95:
            color = 'green'
        elif rate >= 80:
            color = 'orange'
        else:
            color = 'red'
        return format_html(
            '<span style="color: {};">{:.1f}%</span>',
            color, rate
        )
    success_rate_display.short_description = 'Success Rate'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('uploaded_by')
