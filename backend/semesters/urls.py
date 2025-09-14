from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from users.permission import IsAdminUser
from .serializers import SemesterSerializer, CreateSemesterSerializer, SelectViewSerializer
from .models import Semester
from .services import create_semester_db, set_view_semester, set_current_semester

class SemesterListView(APIView):
    permission_classes = [IsAuthenticated]
    def get(self, request):
        qs = Semester.objects.all()
        return Response(SemesterSerializer(qs, many=True).data)

class SemesterCreateView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    def post(self, request):
        s = CreateSemesterSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        sem = create_semester_db(**s.validated_data)
        return Response(SemesterSerializer(sem).data, status=201)

class SemesterSelectView(APIView):
    """
    Set *viewing* semester (read-only). Pass {"alias": null} to revert to current.
    """
    permission_classes = [IsAuthenticated]
    def post(self, request):
        s = SelectViewSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        alias = s.validated_data.get("alias") or None
        if alias and not Semester.objects.filter(alias=alias).exists():
            return Response({"detail": "Unknown alias"}, status=404)
        set_view_semester(request, alias)
        return Response({"ok": True})

class SemesterSetCurrentView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]
    def post(self, request, alias):
        if not Semester.objects.filter(alias=alias).exists():
            return Response({"detail": "Unknown alias"}, status=404)
        set_current_semester(alias)
        return Response({"ok": True})
