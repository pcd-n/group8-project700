from rest_framework import serializers
from .models import Unit, Course, UnitCourse, Skill, UnitSkill


class UnitSerializer(serializers.ModelSerializer):
    """Serializer for Unit model."""
    
    class Meta:
        model = Unit
        fields = ['unit_id', 'unit_code', 'unit_name', 'credits', 'created_at', 'updated_at']
        read_only_fields = ['unit_id', 'created_at', 'updated_at']

    def validate_unit_code(self, value):
        """Validate and normalize unit code."""
        if value:
            value = value.upper().strip()
            if len(value) < 3:
                raise serializers.ValidationError("Unit code must be at least 3 characters long.")
        return value


class CourseSerializer(serializers.ModelSerializer):
    """Serializer for Course model."""
    campus_name = serializers.CharField(source='campus.name', read_only=True)
    
    class Meta:
        model = Course
        fields = ['course_id', 'course_code', 'course_name', 'campus', 'campus_name', 'created_at', 'updated_at']
        read_only_fields = ['course_id', 'created_at', 'updated_at']

    def validate_course_code(self, value):
        """Validate and normalize course code."""
        if value:
            value = value.upper().strip()
            if len(value) < 3:
                raise serializers.ValidationError("Course code must be at least 3 characters long.")
        return value


class SkillSerializer(serializers.ModelSerializer):
    """Serializer for Skill model."""
    
    class Meta:
        model = Skill
        fields = ['skill_id', 'skill_name', 'description', 'created_at', 'updated_at']
        read_only_fields = ['skill_id', 'created_at', 'updated_at']

    def validate_skill_name(self, value):
        """Validate skill name."""
        if value:
            value = value.strip()
            if len(value) < 2:
                raise serializers.ValidationError("Skill name must be at least 2 characters long.")
        return value


class UnitSkillSerializer(serializers.ModelSerializer):
    """Serializer for UnitSkill relationship."""
    unit_code = serializers.CharField(source='unit.unit_code', read_only=True)
    unit_name = serializers.CharField(source='unit.unit_name', read_only=True)
    skill_name = serializers.CharField(source='skill.skill_name', read_only=True)
    
    class Meta:
        model = UnitSkill
        fields = [
            'id', 'unit', 'unit_code', 'unit_name', 'skill', 'skill_name',
            'proficiency_level', 'is_required', 'is_taught', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class UnitCourseSerializer(serializers.ModelSerializer):
    """Serializer for UnitCourse relationship."""
    unit_code = serializers.CharField(source='unit.unit_code', read_only=True)
    unit_name = serializers.CharField(source='unit.unit_name', read_only=True)
    course_code = serializers.CharField(source='course.course_code', read_only=True)
    course_name = serializers.CharField(source='course.course_name', read_only=True)
    campus_name = serializers.CharField(source='campus.name', read_only=True)
    
    class Meta:
        model = UnitCourse
        fields = [
            'unit_course_id', 'unit', 'unit_code', 'unit_name',
            'course', 'course_code', 'course_name',
            'campus', 'campus_name', 'term', 'year', 'status',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['unit_course_id', 'created_at', 'updated_at']

    def validate_term(self, value):
        """Validate and normalize term."""
        if value:
            value = value.upper().strip()
        return value

    def validate_year(self, value):
        """Validate academic year."""
        if value and value < 2020:
            raise serializers.ValidationError("Year must be 2020 or later.")
        return value


class UnitDetailSerializer(UnitSerializer):
    """Detailed serializer for Unit with related data."""
    unit_skills = UnitSkillSerializer(many=True, read_only=True)
    unit_courses = UnitCourseSerializer(many=True, read_only=True)
    
    class Meta(UnitSerializer.Meta):
        fields = UnitSerializer.Meta.fields + ['unit_skills', 'unit_courses']


class CourseDetailSerializer(CourseSerializer):
    """Detailed serializer for Course with related data."""
    course_units = UnitCourseSerializer(many=True, read_only=True)
    
    class Meta(CourseSerializer.Meta):
        fields = CourseSerializer.Meta.fields + ['course_units']


class SkillDetailSerializer(SkillSerializer):
    """Detailed serializer for Skill with related data."""
    skill_units = UnitSkillSerializer(many=True, read_only=True)
    
    class Meta(SkillSerializer.Meta):
        fields = SkillSerializer.Meta.fields + ['skill_units']


# Bulk operation serializers
class BulkUnitCreateSerializer(serializers.Serializer):
    """Serializer for bulk unit creation."""
    units = UnitSerializer(many=True)
    
    def create(self, validated_data):
        units_data = validated_data['units']
        units = []
        for unit_data in units_data:
            unit = Unit.objects.create(**unit_data)
            units.append(unit)
        return {'units': units}


class BulkCourseCreateSerializer(serializers.Serializer):
    """Serializer for bulk course creation."""
    courses = CourseSerializer(many=True)
    
    def create(self, validated_data):
        courses_data = validated_data['courses']
        courses = []
        for course_data in courses_data:
            course = Course.objects.create(**course_data)
            courses.append(course)
        return {'courses': courses}
