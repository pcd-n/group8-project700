from rest_framework import serializers
from django.db import transaction
from django.utils import timezone
from .models import Subject, ActivityGroup, TimetableEntry, TimetableImport, TimeTable
from units.serializers import UnitSerializer
from users.serializers import CampusSerializer, UserSerializer


class SubjectSerializer(serializers.ModelSerializer):
    unit_details = UnitSerializer(source='unit', read_only=True)
    timetable_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Subject
        fields = [
            'subject_code', 'unit', 'unit_details', 'subject_description', 
            'faculty', 'semester', 'year', 'timetable_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ('created_at', 'updated_at')
    
    def get_timetable_count(self, obj):
        """Get count of timetable entries for this subject."""
        return obj.timetable_entries.count()
    
    def validate_subject_code(self, value):
        """Validate subject code format and uniqueness."""
        if not value:
            raise serializers.ValidationError("Subject code is required.")
        
        # Check for uniqueness (excluding current instance for updates)
        queryset = Subject.objects.filter(subject_code=value)
        if self.instance:
            queryset = queryset.exclude(pk=self.instance.pk)
        
        if queryset.exists():
            raise serializers.ValidationError("Subject with this code already exists.")
        
        return value.upper().strip()


class ActivityGroupSerializer(serializers.ModelSerializer):
    timetable_count = serializers.SerializerMethodField()
    
    class Meta:
        model = ActivityGroup
        fields = [
            'activity_group_code', 'activity_type', 'description',
            'timetable_count', 'created_at'
        ]
        read_only_fields = ('created_at',)
    
    def get_timetable_count(self, obj):
        """Get count of timetable entries using this activity group."""
        return obj.timetable_entries.count()


class TimetableEntrySerializer(serializers.ModelSerializer):
    subject_details = SubjectSerializer(source='subject', read_only=True)
    activity_group_details = ActivityGroupSerializer(source='activity_group', read_only=True)
    campus_details = CampusSerializer(source='campus', read_only=True)
    staff_details = UserSerializer(source='staff_member', read_only=True)
    end_time = serializers.ReadOnlyField()
    is_allocated = serializers.ReadOnlyField()
    capacity_utilization = serializers.ReadOnlyField()
    
    class Meta:
        model = TimetableEntry
        fields = [
            'timetable_id', 'subject', 'subject_details', 'activity_group', 
            'activity_group_details', 'activity_code', 'campus', 'campus_details',
            'day_of_week', 'start_time', 'end_time', 'duration', 'weeks', 
            'teaching_weeks', 'location', 'size', 'buffer', 'adjusted_size', 
            'student_count', 'constraint_count', 'staff_member', 'staff_details',
            'staff_name', 'show_on_timetable', 'available_for_allocation',
            'cluster', 'group', 'activity_description', 'is_allocated',
            'capacity_utilization', 'created_at', 'updated_at', 'imported_at'
        ]
        read_only_fields = ('timetable_id', 'created_at', 'updated_at', 'imported_at')
    
    def validate(self, data):
        """Validate timetable entry data."""
        # Validate time constraints
        if data.get('duration', 0) <= 0:
            raise serializers.ValidationError("Duration must be greater than 0.")
        
        if data.get('teaching_weeks', 0) <= 0:
            raise serializers.ValidationError("Teaching weeks must be greater than 0.")
        
        # Validate capacity constraints
        size = data.get('size', 0)
        buffer = data.get('buffer', 0)
        adjusted_size = data.get('adjusted_size', 0)
        student_count = data.get('student_count', 0)
        
        expected_adjusted_size = size + buffer
        if adjusted_size != expected_adjusted_size:
            data['adjusted_size'] = expected_adjusted_size
        
        if student_count > adjusted_size:
            raise serializers.ValidationError(
                f"Student count ({student_count}) cannot exceed adjusted size ({adjusted_size})."
            )
        
        # Validate unique constraint for subject + activity_code
        subject = data.get('subject')
        activity_code = data.get('activity_code')
        
        if subject and activity_code:
            queryset = TimetableEntry.objects.filter(
                subject=subject, 
                activity_code=activity_code
            )
            if self.instance:
                queryset = queryset.exclude(pk=self.instance.pk)
            
            if queryset.exists():
                raise serializers.ValidationError(
                    f"Timetable entry with subject {subject.subject_code} and "
                    f"activity code {activity_code} already exists."
                )
        
        return data
    
    def validate_staff_assignment(self, staff_member):
        """Validate staff member assignment."""
        if staff_member and not staff_member.is_active:
            raise serializers.ValidationError("Cannot assign inactive staff member.")
        
        return staff_member


class TimetableImportSerializer(serializers.ModelSerializer):
    uploaded_by_details = UserSerializer(source='uploaded_by', read_only=True)
    success_rate = serializers.ReadOnlyField()
    
    class Meta:
        model = TimetableImport
        fields = [
            'import_id', 'filename', 'uploaded_by', 'uploaded_by_details',
            'status', 'total_rows', 'processed_rows', 'error_rows',
            'success_rate', 'error_log', 'created_at', 'completed_at'
        ]
        read_only_fields = (
            'import_id', 'total_rows', 'processed_rows', 'error_rows',
            'error_log', 'created_at', 'completed_at'
        )


class TimetableBulkImportSerializer(serializers.Serializer):
    """
    Serializer for bulk importing timetable data from CSV.
    """
    csv_file = serializers.FileField(
        help_text="CSV file containing timetable data"
    )
    overwrite_existing = serializers.BooleanField(
        default=False,
        help_text="Whether to overwrite existing entries with same subject+activity_code"
    )
    
    def validate_csv_file(self, value):
        """Validate the uploaded CSV file."""
        if not value.name.endswith('.csv'):
            raise serializers.ValidationError("File must be a CSV file.")
        
        # Check file size (limit to 50MB)
        if value.size > 50 * 1024 * 1024:
            raise serializers.ValidationError("File size cannot exceed 50MB.")
        
        return value
    
    def create(self, validated_data):
        """Process the CSV file and create timetable entries."""
        csv_file = validated_data['csv_file']
        overwrite_existing = validated_data['overwrite_existing']
        user = self.context['request'].user
        
        # Create import record
        import_record = TimetableImport.objects.create(
            filename=csv_file.name,
            uploaded_by=user,
            status='Processing'
        )
        
        try:
            # Process CSV file (this would be implemented as a separate function)
            result = self._process_csv_file(csv_file, overwrite_existing, import_record)
            
            import_record.status = 'Completed'
            import_record.total_rows = result['total_rows']
            import_record.processed_rows = result['processed_rows']
            import_record.error_rows = result['error_rows']
            import_record.error_log = result['error_log']
            import_record.completed_at = timezone.now()
            import_record.save()
            
            return import_record
            
        except Exception as e:
            import_record.status = 'Failed'
            import_record.error_log = str(e)
            import_record.completed_at = timezone.now()
            import_record.save()
            raise serializers.ValidationError(f"Import failed: {str(e)}")
    
    def _process_csv_file(self, csv_file, overwrite_existing, import_record):
        """
        Process the CSV file and create timetable entries.
        This is a placeholder for the actual CSV processing logic.
        """
        import csv
        from io import TextIOWrapper
        
        # Wrap the file for text reading
        csv_file.seek(0)
        file_wrapper = TextIOWrapper(csv_file, encoding='utf-8')
        csv_reader = csv.DictReader(file_wrapper)
        
        total_rows = 0
        processed_rows = 0
        error_rows = 0
        error_log = []
        
        with transaction.atomic():
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 to account for header
                total_rows += 1
                
                try:
                    # Process each row here
                    # This would involve parsing the CSV data and creating TimetableEntry objects
                    # For now, this is a placeholder
                    processed_rows += 1
                    
                except Exception as e:
                    error_rows += 1
                    error_log.append(f"Row {row_num}: {str(e)}")
        
        return {
            'total_rows': total_rows,
            'processed_rows': processed_rows,
            'error_rows': error_rows,
            'error_log': '\n'.join(error_log)
        }

class TimeTableSessionSerializer(serializers.ModelSerializer):
    session_id = serializers.IntegerField(source="id", read_only=True)
    activity_code = serializers.CharField(source="activity_code", required=False)
    campus = serializers.CharField(required=False)
    day_of_week = serializers.CharField(source="day", required=False)
    start_time = serializers.CharField(required=False)
    duration = serializers.IntegerField(required=False)
    location = serializers.CharField(required=False)
    weeks = serializers.CharField(required=False)
    staff = serializers.SerializerMethodField()

    class Meta:
        model = TimeTable
        fields = ["session_id","activity_code","campus","day_of_week",
                  "start_time","duration","location","weeks","staff"]

    def get_staff(self, obj):
        # If you already create Allocation rows, return the names on this slot:
        # obj.allocations is Allocation queryset via related_name="allocations"
        return [alloc.tutor.get_full_name() or alloc.tutor.email for alloc in obj.allocations.all()]