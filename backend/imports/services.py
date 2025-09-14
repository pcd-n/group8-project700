import io
import pandas as pd
from django.utils import timezone
from django.db import transaction
from users.models import User, Campus
from units.models import Unit, UnitCourse, Course
from timetable.models import MasterClassTime, TimeTable
from eoi.models import EoiApp  # your SCD-II model

# Helpers
def _norm(s):
    if pd.isna(s):
        return None
    if isinstance(s, str):
        return s.strip()
    return s

def _parse_time(x):
    if pd.isna(x):
        return None
    # handle 9:00 / 09:00 / datetime.time etc.
    if hasattr(x, "hour"):
        return x
    try:
        return pd.to_datetime(str(x)).time()
    except Exception:
        return None

def _choice_day(s):
    # Map free-text to your DAY_CHOICES in TimeTable
    m = {"MON":"MON","TUE":"TUE","WED":"WED","THU":"THU","FRI":"FRI","SAT":"SAT","SUN":"SUN"}
    key = str(s or "").strip().upper()[:3]
    return m.get(key)

# ========== EOI import ==========
@transaction.atomic
def import_eoi_xlsx(fobj, job):
    """
    Accepts either 'Casual Master EOI Spreadsheet.xlsx' or 'Casual EOI Spreadsheet.xlsx'.
    Expected columns (best-effort, tolerant to naming):
    - TutorEmail / Email
    - UnitCode
    - Preference (1,2,3…)
    - Campus (SB/IR/Hobart/Launceston)
    - Qualifications
    - Availability
    """
    df = pd.read_excel(fobj, engine="openpyxl")
    job.rows_total = len(df.index)

    col = {c.lower().strip(): c for c in df.columns}
    get = lambda *names: next((col[n.lower()] for n in names if n.lower() in col), None)

    c_email = get("TutorEmail","Email","applicant","applicant_email")
    c_unit  = get("UnitCode","Unit","Unit Code")
    c_pref  = get("Preference","Rank","Priority")
    c_campus= get("Campus","Location")
    c_qua   = get("Qualifications","Notes","Experience")
    c_avail = get("Availability","Available","Times")

    ok = err = 0
    logs = []

    for i, row in df.iterrows():
        try:
            email = _norm(row.get(c_email)) if c_email else None
            unit_code = _norm(row.get(c_unit)) if c_unit else None
            pref = int(row.get(c_pref)) if c_pref and pd.notna(row.get(c_pref)) else 0
            campus_name = _norm(row.get(c_campus)) if c_campus else None
            qual = _norm(row.get(c_qua)) if c_qua else ""
            avail = _norm(row.get(c_avail)) if c_avail else ""

            if not email or not unit_code:
                raise ValueError("Missing email/unit")

            user = User.objects.filter(email__iexact=email).first()
            if not user:
                raise ValueError(f"User not found: {email}")

            unit = Unit.objects.filter(unit_code__iexact=unit_code).first()
            if not unit:
                raise ValueError(f"Unit not found: {unit_code}")

            campus = None
            if campus_name:
                campus = Campus.objects.filter(campus_name__iexact=campus_name).first()

            # Pick the current UnitCourse if any (S2/Year match not provided here)
            uc = UnitCourse.objects.filter(unit=unit).order_by("-year","-created_at").first()

            # Create/append SCD-II row: use business key eoi_app_id per your model logic
            app = EoiApp(
                applicant_user=user,
                unit=unit,
                campus=campus,
                status="Submitted",
                remarks="Imported from spreadsheet",
                preference=pref,
                qualifications=qual,
                availability=avail,
            )
            app.save()  # model handles versioning
            ok += 1
        except Exception as ex:
            err += 1
            logs.append(f"Row {i+2}: {ex}")

    job.rows_ok = ok
    job.rows_error = err
    job.log = "\n".join(logs)
    job.ok = err == 0
    job.finished_at = timezone.now()
    job.save()
    return job

# ========== Master Classes import ==========
@transaction.atomic
def import_master_classes_xlsx(fobj, job):
    """
    Parse 'Master class List.xlsx' into MasterClassTime.
    Important fields in your table: subject_code, activity_code, campus, day_of_week,
    start_time, duration, size, buffer, adjusted_size, etc.  :contentReference[oaicite:2]{index=2}
    """
    df = pd.read_excel(fobj, engine="openpyxl")
    job.rows_total = len(df.index)
    col = {c.lower().strip(): c for c in df.columns}
    get = lambda *names: next((col[n.lower()] for n in names if n.lower() in col), None)

    c_subj = get("Subject Code","SubjectCode","Unit Code","UnitCode")
    c_desc = get("Subject Description","Description")
    c_fac  = get("Faculty")
    c_group= get("Activity Group Code","Group")
    c_act  = get("Activity Code","Activity")
    c_actd = get("Activity Description")
    c_camp = get("Campus")
    c_loc  = get("Location","Room")
    c_day  = get("Day","Day of Week")
    c_start= get("Start","Start Time")
    c_weeks= get("Weeks")
    c_teach= get("Teaching Weeks","TeachingWeeks")
    c_dur  = get("Duration","Duration (mins)")
    c_staff= get("Staff")
    c_size = get("Size","Capacity")
    c_buff = get("Buffer")
    c_adj  = get("Adjusted Size","AdjustedSize")
    c_stu  = get("Student Count","Students")
    c_con  = get("Constraint Count","Constraints")
    c_cluster = get("Cluster")
    c_group2  = get("Group Code","Group")

    ok = err = 0
    logs = []

    for i, row in df.iterrows():
        try:
            m = MasterClassTime(
                subject_code=_norm(row.get(c_subj)),
                subject_description=_norm(row.get(c_desc)) or "",
                faculty=_norm(row.get(c_fac)) or "",
                activity_group_code=_norm(row.get(c_group)) or "",
                activity_code=_norm(row.get(c_act)) or "",
                activity_description=_norm(row.get(c_actd)) or "",
                campus=_norm(row.get(c_camp)) or "",
                location=_norm(row.get(c_loc)) or "",
                day_of_week=_norm(row.get(c_day)) or "",
                start_time=_parse_time(row.get(c_start)),
                weeks=_norm(row.get(c_weeks)) or "",
                teaching_weeks=int(row.get(c_teach) or 0),
                duration=int(row.get(c_dur) or 0),
                staff=_norm(row.get(c_staff)) or "",
                size=int(row.get(c_size) or 0),
                buffer=int(row.get(c_buff) or 0),
                adjusted_size=int(row.get(c_adj) or 0),
                student_count=int(row.get(c_stu) or 0),
                constraint_count=int(row.get(c_con) or 0),
                cluster=_norm(row.get(c_cluster)) or "",
                group=_norm(row.get(c_group2)) or "",
                show_on_timetable=True,
                available_for_allocation=True,
            )
            # upsert by unique (subject_code, activity_code, campus) per your model constraint :contentReference[oaicite:3]{index=3}
            MasterClassTime.objects.update_or_create(
                subject_code=m.subject_code, activity_code=m.activity_code, campus=m.campus,
                defaults=m.__dict__
            )
            ok += 1
        except Exception as ex:
            err += 1
            logs.append(f"Row {i+2}: {ex}")

    job.rows_ok = ok
    job.rows_error = err
    job.log = "\n".join(logs)
    job.ok = err == 0
    job.finished_at = timezone.now()
    job.save()
    return job

# ========== Tutorial Allocations seed (optional) ==========
@transaction.atomic
def import_tutorial_allocations_xlsx(fobj, job):
    """
    Optionally seed TimeTable rows from a “Tutorial Allocations.xlsx”
    (one row per class slot), mapping staff into `tutor_user` when email matches.
    Table & fields per your TimeTable model.  :contentReference[oaicite:4]{index=4}
    """
    df = pd.read_excel(fobj, engine="openpyxl")
    job.rows_total = len(df.index)
    col = {c.lower().strip(): c for c in df.columns}
    get = lambda *names: next((col[n.lower()] for n in names if n.lower() in col), None)

    c_unit  = get("UnitCode","Unit Code")
    c_course= get("CourseCode","Course")
    c_campus= get("Campus")
    c_room  = get("Room","Location")
    c_day   = get("Day")
    c_start = get("Start","Start Time")
    c_end   = get("End","End Time")
    c_staff = get("Staff","TutorEmail","Tutor")

    ok = err = 0
    logs = []

    for i, row in df.iterrows():
        try:
            unit_code = _norm(row.get(c_unit))
            course_code = _norm(row.get(c_course))
            campus_name = _norm(row.get(c_campus))
            day = _choice_day(row.get(c_day))
            start = _parse_time(row.get(c_start))
            end = _parse_time(row.get(c_end))
            room = _norm(row.get(c_room)) or ""

            unit = Unit.objects.filter(unit_code__iexact=unit_code).first()
            course = Course.objects.filter(course_code__iexact=course_code).first()
            campus = Campus.objects.filter(campus_name__iexact=campus_name).first()

            if not (unit and course and campus and day and start and end):
                raise ValueError("Missing unit/course/campus/day/time")

            uc = UnitCourse.objects.filter(unit=unit, course=course, campus=campus).order_by("-year").first()
            if not uc:
                raise ValueError("UnitCourse not found")

            tutor_user = None
            staff_val = _norm(row.get(c_staff))
            if staff_val and "@" in staff_val:
                tutor_user = User.objects.filter(email__iexact=staff_val).first()

            # create or update slot uniqueness per constraint (unit_course, campus, day_of_week, start_time)
            slot, _ = TimeTable.objects.update_or_create(
                unit_course=uc,
                campus=campus,
                day_of_week=day,
                start_time=start,
                defaults=dict(room=room, end_time=end, tutor_user=tutor_user),
            )
            ok += 1
        except Exception as ex:
            err += 1
            logs.append(f"Row {i+2}: {ex}")

    job.rows_ok = ok
    job.rows_error = err
    job.log = "\n".join(logs)
    job.ok = err == 0
    job.finished_at = timezone.now()
    job.save()
    return job
