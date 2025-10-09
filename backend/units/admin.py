from django.contrib import admin
from .models import Unit, Course, UnitCourse, Skill, UnitSkill


@admin.register(Unit)
class UnitAdmin(admin.ModelAdmin):
    list_display = ['unit_code', 'unit_name', 'credits', 'created_at']
    list_filter = ['credits', 'created_at']
    search_fields = ['unit_code', 'unit_name']
    ordering = ['unit_code']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['course_code', 'course_name', 'campus', 'created_at']
    list_filter = ['campus', 'created_at']
    search_fields = ['course_code', 'course_name']
    ordering = ['course_code']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(UnitCourse)
class UnitCourseAdmin(admin.ModelAdmin):
    list_display = ['unit', 'course', 'campus', 'term', 'year', 'status']
    list_filter = ['status', 'year', 'term', 'campus', 'created_at']
    search_fields = ['unit__unit_code', 'unit__unit_name', 'course__course_code', 'course__course_name']
    ordering = ['-year', 'term', 'unit__unit_code']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('unit', 'course', 'status')
        }),
        ('Delivery Details', {
            'fields': ('campus', 'term', 'year')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ['skill_name', 'description', 'created_at']
    search_fields = ['skill_name', 'description']
    ordering = ['skill_name']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(UnitSkill)
class UnitSkillAdmin(admin.ModelAdmin):
    list_display = ['unit', 'skill', 'proficiency_level', 'is_required', 'is_taught']
    list_filter = ['proficiency_level', 'is_required', 'is_taught', 'created_at']
    search_fields = ['unit__unit_code', 'unit__unit_name', 'skill__skill_name']
    ordering = ['unit__unit_code', 'skill__skill_name']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Relationship', {
            'fields': ('unit', 'skill')
        }),
        ('Skill Details', {
            'fields': ('proficiency_level', 'is_required', 'is_taught')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
