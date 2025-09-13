from rest_framework import serializers
from .models import EoiApp, MasterEoI, TutorsCourses, TutorSkills, TutorSupervisors


class EoiAppSerializer(serializers.ModelSerializer):
    """Serializer for EoiApp model."""
    applicant_email = serializers.CharField(source='applicant_user.email', read_only=True)
    applicant_name = serializers.SerializerMethodField()
    unit_code = serializers.CharField(source='unit.unit_code', read_only=True)
    unit_name = serializers.CharField(source='unit.unit_name', read_only=True)
    campus_name = serializers.CharField(source='campus.campus_name', read_only=True)
    
    class Meta:
        model = EoiApp
        fields = [
            'scd_id', 'eoi_app_id', 'applicant_user', 'applicant_email', 'applicant_name',
            'unit', 'unit_code', 'unit_name', 'campus', 'campus_name',
            'status', 'remarks', 'valid_from', 'valid_to', 'is_current', 'version',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['scd_id', 'eoi_app_id', 'valid_from', 'valid_to', 'is_current', 'version', 'created_at', 'updated_at']
    
    def get_applicant_name(self, obj):
        """Get full name of applicant."""
        return obj.applicant_user.get_full_name()
    
    def validate_status(self, value):
        """Validate status transitions."""
        if self.instance:
            current_status = self.instance.status
            valid_transitions = {
                'Submitted': ['Reviewed', 'Rejected'],
                'Reviewed': ['Accepted', 'Rejected'],
                'Accepted': ['Rejected'],  # Can be revoked
                'Rejected': []  # Terminal state
            }
            
            if value != current_status and value not in valid_transitions.get(current_status, []):
                raise serializers.ValidationError(
                    f"Invalid status transition from '{current_status}' to '{value}'"
                )
        
        return value


class MasterEoISerializer(serializers.ModelSerializer):
    """Serializer for MasterEoI model."""
    owner_email = serializers.CharField(source='owner_user.email', read_only=True)
    owner_name = serializers.SerializerMethodField()
    course_code = serializers.CharField(source='course.course_code', read_only=True)
    course_name = serializers.CharField(source='course.course_name', read_only=True)
    campus_name = serializers.CharField(source='campus.campus_name', read_only=True)
    
    class Meta:
        model = MasterEoI
        fields = [
            'scd_id', 'master_eoi_id', 'owner_user', 'owner_email', 'owner_name',
            'course', 'course_code', 'course_name', 'campus', 'campus_name',
            'intake_term', 'status', 'notes', 'valid_from', 'valid_to', 
            'is_current', 'version', 'created_at', 'updated_at'
        ]
        read_only_fields = ['scd_id', 'master_eoi_id', 'valid_from', 'valid_to', 'is_current', 'version', 'created_at', 'updated_at']
    
    def get_owner_name(self, obj):
        """Get full name of owner."""
        return obj.owner_user.get_full_name()
    
    def validate_intake_term(self, value):
        """Validate intake term format."""
        if value:
            # Basic validation for format like 2025S1, 2025S2
            import re
            if not re.match(r'^\d{4}S[1-2]$', value):
                raise serializers.ValidationError(
                    "Intake term must be in format YYYYS1 or YYYYS2 (e.g., 2025S1)"
                )
        return value


class TutorsCoursesSerializer(serializers.ModelSerializer):
    """Serializer for TutorsCourses model."""
    tutor_email = serializers.CharField(source='tutor_user.email', read_only=True)
    tutor_name = serializers.SerializerMethodField()
    course_code = serializers.CharField(source='course.course_code', read_only=True)
    course_name = serializers.CharField(source='course.course_name', read_only=True)
    
    class Meta:
        model = TutorsCourses
        fields = [
            'id', 'tutor_user', 'tutor_email', 'tutor_name',
            'course', 'course_code', 'course_name', 'assigned_at'
        ]
        read_only_fields = ['id', 'assigned_at']
    
    def get_tutor_name(self, obj):
        """Get full name of tutor."""
        return obj.tutor_user.get_full_name()
    
    def validate(self, data):
        """Validate unique constraint."""
        tutor_user = data.get('tutor_user')
        course = data.get('course')
        
        if tutor_user and course:
            existing = TutorsCourses.objects.filter(
                tutor_user=tutor_user,
                course=course
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                raise serializers.ValidationError(
                    "This tutor is already assigned to this course."
                )
        
        return data


class TutorSkillsSerializer(serializers.ModelSerializer):
    """Serializer for TutorSkills model."""
    tutor_email = serializers.CharField(source='tutor_user.email', read_only=True)
    tutor_name = serializers.SerializerMethodField()
    skill_name = serializers.CharField(source='skill.skill_name', read_only=True)
    verified_by_email = serializers.CharField(source='verified_by.email', read_only=True)
    verified_by_name = serializers.SerializerMethodField()
    
    class Meta:
        model = TutorSkills
        fields = [
            'id', 'tutor_user', 'tutor_email', 'tutor_name',
            'skill', 'skill_name', 'level', 'verified_by', 'verified_by_email',
            'verified_by_name', 'verified_at', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_tutor_name(self, obj):
        """Get full name of tutor."""
        return obj.tutor_user.get_full_name()
    
    def get_verified_by_name(self, obj):
        """Get full name of verifier."""
        return obj.verified_by.get_full_name() if obj.verified_by else None
    
    def validate(self, data):
        """Validate unique constraint and verification logic."""
        tutor_user = data.get('tutor_user')
        skill = data.get('skill')
        verified_by = data.get('verified_by')
        verified_at = data.get('verified_at')
        
        if tutor_user and skill:
            existing = TutorSkills.objects.filter(
                tutor_user=tutor_user,
                skill=skill
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                raise serializers.ValidationError(
                    "This tutor already has this skill recorded."
                )
        
        # Verification logic
        if verified_by and not verified_at:
            from django.utils import timezone
            data['verified_at'] = timezone.now()
        elif not verified_by and verified_at:
            raise serializers.ValidationError(
                "Cannot set verified_at without verified_by."
            )
        
        return data


class TutorSupervisorsSerializer(serializers.ModelSerializer):
    """Serializer for TutorSupervisors model."""
    tutor_email = serializers.CharField(source='tutor_user.email', read_only=True)
    tutor_name = serializers.SerializerMethodField()
    supervisor_email = serializers.CharField(source='supervisor.user.email', read_only=True)
    supervisor_name = serializers.SerializerMethodField()
    supervisor_campus = serializers.CharField(source='supervisor.campus.campus_name', read_only=True)
    
    class Meta:
        model = TutorSupervisors
        fields = [
            'id', 'tutor_user', 'tutor_email', 'tutor_name',
            'supervisor', 'supervisor_email', 'supervisor_name', 'supervisor_campus',
            'assigned_at'
        ]
        read_only_fields = ['id', 'assigned_at']
    
    def get_tutor_name(self, obj):
        """Get full name of tutor."""
        return obj.tutor_user.get_full_name()
    
    def get_supervisor_name(self, obj):
        """Get full name of supervisor."""
        return obj.supervisor.user.get_full_name()
    
    def validate(self, data):
        """Validate unique constraint."""
        tutor_user = data.get('tutor_user')
        supervisor = data.get('supervisor')
        
        if tutor_user and supervisor:
            existing = TutorSupervisors.objects.filter(
                tutor_user=tutor_user,
                supervisor=supervisor
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                raise serializers.ValidationError(
                    "This tutor is already assigned to this supervisor."
                )
        
        return data


# Detailed serializers with nested data
class EoiAppDetailSerializer(EoiAppSerializer):
    """Detailed serializer for EoiApp with related data."""
    unit_details = serializers.SerializerMethodField()
    campus_details = serializers.SerializerMethodField()
    
    class Meta(EoiAppSerializer.Meta):
        fields = EoiAppSerializer.Meta.fields + ['unit_details', 'campus_details']
    
    def get_unit_details(self, obj):
        """Get unit details."""
        if obj.unit:
            return {
                'unit_id': obj.unit.unit_id,
                'unit_code': obj.unit.unit_code,
                'unit_name': obj.unit.unit_name,
                'credits': obj.unit.credits
            }
        return None
    
    def get_campus_details(self, obj):
        """Get campus details."""
        if obj.campus:
            return {
                'campus_name': obj.campus.campus_name,
                'campus_location': obj.campus.campus_location
            }
        return None


class MasterEoIDetailSerializer(MasterEoISerializer):
    """Detailed serializer for MasterEoI with related data."""
    course_details = serializers.SerializerMethodField()
    campus_details = serializers.SerializerMethodField()
    applications_count = serializers.SerializerMethodField()
    
    class Meta(MasterEoISerializer.Meta):
        fields = MasterEoISerializer.Meta.fields + ['course_details', 'campus_details', 'applications_count']
    
    def get_course_details(self, obj):
        """Get course details."""
        if obj.course:
            return {
                'course_id': obj.course.course_id,
                'course_code': obj.course.course_code,
                'course_name': obj.course.course_name
            }
        return None
    
    def get_campus_details(self, obj):
        """Get campus details."""
        if obj.campus:
            return {
                'campus_name': obj.campus.campus_name,
                'campus_location': obj.campus.campus_location
            }
        return None
    
    def get_applications_count(self, obj):
        """Count related EOI applications."""
        # This would need a proper relationship setup between MasterEoI and EoiApp
        return 0  # Placeholder for now
