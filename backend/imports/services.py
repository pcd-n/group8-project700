# imports/services.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Tuple
import re
import uuid

import pandas as pd
from django.db import transaction
from django.utils import timezone

# --- Project models (adjust imports only if your paths differ) ---
from users.models import User, Campus
from units.models import Unit, Course, UnitCourse
from eoi.models import EoiApp
from timetable.models import MasterClassTime, Timetable, TimetableImportLog


# =========================
# Header validation helpers
# =========================

REQUIRED_COLUMNS: Dict[str, set[str]] = {
    "eoi": {
        "tutor_email",
        "unit_code",
        "preference",
        "campus",
        "qualifications",
        "availability",
    },
    "master_classes": {
        "subject_code",
        "subject_description",
        "activity_group_code",
        "activity_code",
        "activity_description",
        "campus",
        "location",
        "day_of_week",
        "start_time",
        "weeks",
        "staff",
        "size",
    },
    "tutorial_allocations": {
        "unit_code",
        "day_of_week",
        "start_time",
        "end_time",
        "room",
        "tutor_email",
    },
}

# Flexible synonyms so slightly different headers still map correctly
HEADER_SYNONYMS: Dict[str, set[str]] = {
    # generic
    "tutor_email": {"TutorEmail", "Email", "Applicant", "ApplicantEmail", "applicant", "applicant_email"},
    "unit_code": {"UnitCode", "Unit", "Unit Code", "subject_code"},
    "preference": {"Preference", "Rank", "Priority"},
    "campus": {"Campus", "Location"},
    "qualifications": {"Qualifications", "Notes", "Experience"},
    "availability": {"Availability", "Available", "Times"},
    # master classes
    "subject_description": {"SubjectDescription", "Subject Name", "Unit Name"},
    "activity_group_code": {"ActivityGroup", "GroupCode", "Group"},
    "activity_code": {"ActivityCode", "Activity"},
    "activity_description": {"ActivityDescription", "Activity Desc"},
    "location": {"Location", "RoomLocation"},
    "day_of_week": {"Day", "DayOfWeek"},
    "start_time": {"Start", "StartTime"},
    "weeks": {"Weeks", "TeachingWeeks"},
    "staff": {"Staff", "StaffName", "Lecturer"},
    "size": {"Size", "Capacity"},
    "end_time": {"End", "EndTime"},
    "room": {"Room", "Location"},
}


def _strip(s) -> str:
    return str(s).strip() if s is not None else ""


def _normalise_headers(df: pd.DataFrame) -> Dict[str, str]:
    """
    Returns a mapping {wanted_key -> actual_column_name_in_df}
    """
    mapping: Dict[str, str] = {}
    dfcols = [str(c).strip() for c in df.columns]
    lower_to_actual = {c.lower(): c for c in dfcols}

    for want in set().union(*REQUIRED_COLUMNS.values()) | set(HEADER_SYNONYMS.keys()):
        # exact lowercase match
        if want.lower() in lower_to_actual:
            mapping[want] = lower_to_actual[want.lower()]
            continue
        # synonyms
        for syn in HEADER_SYNONYMS.get(want, set()):
            if syn in dfcols:
                mapping[want] = syn
                break
    return mapping


def _validate_headers(kind: str, df: pd.DataFrame) -> Dict[str, str]:
    mapping = _normalise_headers(df)
    missing = [c for c in REQUIRED_COLUMNS[kind] if c not in mapping]
    if missing:
        raise ValueError(
            f"Spreadsheet is missing required columns for '{kind}': {', '.join(missing)}"
        )
    return mapping


# ============
# Conversions
# ============

DAY_ALIASES = {
    "mon": "Monday",
    "monday": "Monday",
    "tue": "Tuesday",
    "tues": "Tuesday",
    "tuesday": "Tuesday",
    "wed": "Wednesday",
    "wednesday": "Wednesday",
    "thu": "Thursday",
    "thur": "Thursday",
    "thurs": "Thursday",
    "thursday": "Thursday",
    "fri": "Friday",
    "friday": "Friday",
    "sat": "Saturday",
    "saturday": "Saturday",
    "sun": "Sunday",
    "sunday": "Sunday",
}


def _as_day_name(s: str) -> str:
    if not s:
        return s
    key = s.strip().lower()
    return DAY_ALIASES.get(key, s.strip())


def _as_time(cell) -> str:
    """
    Return 'HH:MM:SS' string; supports Excel/strings/pandas time.
    """
    if pd.isna(cell):
        return None
    # If already a time-like string
    text = str(cell).strip()
    m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(am|pm)?$", text, re.IGNORECASE)
    if m:
        h = int(m.group(1))
        mi = int(m.group(2))
        se = int(m.group(3) or 0)
        ampm = m.group(4)
        if ampm:
            ampm = ampm.lower()
            if ampm == "pm" and h < 12:
                h += 12
            if ampm == "am" and h == 12:
                h = 0
        return f"{h:02d}:{mi:02d}:{se:02d}"
    # pandas datetime/time
    try:
        ts = pd.to_datetime(cell)
        return ts.strftime("%H:%M:%S")
    except Exception:
        return text  # last resort; DB layer may still coerce


# ==================
# Logging to control
# ==================

@dataclass
class ImportStats:
    ok: int = 0
    err: int = 0
    errors: list[str] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []

    def log(self, msg: str):
        self.errors.append(msg)
        self.err += 1

    def inc(self):
        self.ok += 1


def _create_log(filename: str, uploaded_by: User) -> TimetableImportLog:
    # Keep logs on default DB
    return TimetableImportLog.objects.create(
        import_id=uuid.uuid4(),
        filename=filename,
        status="RUNNING",
        total_rows=0,
        processed_rows=0,
        error_rows=0,
        error_log="",
        uploaded_by=uploaded_by,
        created_at=timezone.now(),
    )


def _finalise_log(log: TimetableImportLog, stats: ImportStats, total: int, ok_status: str):
    log.total_rows = total
    log.processed_rows = stats.ok
    log.error_rows = stats.err
    log.error_log = "\n".join(stats.errors)
    log.status = "COMPLETED" if stats.err == 0 else "COMPLETED_WITH_ERRORS"
    log.completed_at = timezone.now()
    log.save(update_fields=[
        "total_rows", "processed_rows", "error_rows", "error_log", "status", "completed_at"
    ])


# ================
# EOI import logic
# ================

def import_eoi_xlsx(file_like, job, using: str):
    """
    Import EOI applications.
    Writes go to semester DB given by `using`.
    The job object itself (and log) remains on default DB.
    """
    df = pd.read_excel(file_like)
    col = _validate_headers("eoi", df)

    stats = ImportStats()
    log = _create_log(getattr(job.file, "name", "eoi.xlsx"), job.created_by)

    total = len(df)
    for i, row in df.iterrows():
        try:
            email = _strip(row[col["tutor_email"]]).lower()
            unit_code = _strip(row[col["unit_code"]])
            campus_name = _strip(row[col["campus"]])
            pref = int(row[col["preference"]]) if pd.notna(row[col["preference"]]) else None
            quals = _strip(row[col["qualifications"]])
            avail = _strip(row[col["availability"]])

            if not email or not unit_code:
                raise ValueError("Missing tutor_email or unit_code")

            user = User.objects.filter(email__iexact=email).first()
            if not user:
                raise ValueError(f"No user with email {email}")

            unit = Unit.objects.using(using).filter(unit_code__iexact=unit_code).first()
            if not unit:
                # try default units if shared
                unit = Unit.objects.filter(unit_code__iexact=unit_code).first()
            if not unit:
                raise ValueError(f"No unit '{unit_code}'")

            campus = None
            if campus_name:
                campus = Campus.objects.filter(campus_name__iexact=campus_name).first()

            # Upsert by (applicant_user, unit) as a reasonable natural key
            defaults = {
                "status": "Submitted",
                "remarks": "",
                "valid_from": timezone.now(),
                "is_current": True,
                "version": 1,
                "campus": campus,
                "availability": avail or None,
                "preference": pref or 0,
                "qualifications": quals or None,
                "updated_at": timezone.now(),
                "created_at": timezone.now(),
            }
            # ensure .using(using) writes into semester DB
            EoiApp.objects.using(using).update_or_create(
                applicant_user=user,
                unit=unit,
                defaults=defaults,
            )
            stats.inc()
        except Exception as ex:
            stats.log(f"Row {i + 2}: {ex}")

    _finalise_log(log, stats, total, ok_status="EOI")
    job.rows_ok = stats.ok
    job.rows_error = stats.err
    job.ok = stats.err == 0
    job.finished_at = timezone.now()
    job.save(update_fields=["rows_ok", "rows_error", "ok", "finished_at"])


# ===========================
# Master class times (MCT) import
# ===========================

def import_master_classes_xlsx(file_like, job, using: str):
    """
    Import MasterClassTime rows (teaching activities/timetable templates).
    """
    df = pd.read_excel(file_like)
    col = _validate_headers("master_classes", df)

    stats = ImportStats()
    log = _create_log(getattr(job.file, "name", "master_classes.xlsx"), job.created_by)

    total = len(df)
    for i, row in df.iterrows():
        try:
            subject_code = _strip(row[col["subject_code"]])
            subject_description = _strip(row[col["subject_description"]])
            activity_group_code = _strip(row[col["activity_group_code"]])
            activity_code = _strip(row[col["activity_code"]])
            activity_description = _strip(row[col["activity_description"]])
            campus = _strip(row[col["campus"]])
            location = _strip(row[col["location"]])
            day = _as_day_name(_strip(row[col["day_of_week"]]))
            start = _as_time(row[col["start_time"]])
            weeks = _strip(row[col["weeks"]])
            staff = _strip(row[col["staff"]])
            size = int(row[col["size"]]) if pd.notna(row[col["size"]]) else 0

            if not subject_code or not activity_group_code or not activity_code or not day or not start:
                raise ValueError("Missing one of required identifying fields")

            # Use a natural key for upsert
            lookup = dict(
                subject_code=subject_code,
                activity_group_code=activity_group_code,
                activity_code=activity_code,
                day_of_week=day,
                start_time=start,
            )
            defaults = dict(
                subject_description=subject_description,
                activity_description=activity_description,
                campus=campus,
                location=location,
                weeks=weeks,
                staff=staff,
                size=size,
                # sensible defaults for nullable/extra fields
                faculty="",
                duration=0,
                buffer=0,
                adjusted_size=size,
                student_count=0,
                constraint_count=0,
                cluster="",
                group="",
                show_on_timetable=True,
                available_for_allocation=True,
                updated_at=timezone.now(),
                created_at=timezone.now(),
            )
            MasterClassTime.objects.using(using).update_or_create(
                **lookup, defaults=defaults
            )
            stats.inc()
        except Exception as ex:
            stats.log(f"Row {i + 2}: {ex}")

    _finalise_log(log, stats, total, ok_status="MASTER_CLASSES")
    job.rows_ok = stats.ok
    job.rows_error = stats.err
    job.ok = stats.err == 0
    job.finished_at = timezone.now()
    job.save(update_fields=["rows_ok", "rows_error", "ok", "finished_at"])


# ===========================
# Tutorial allocations import
# ===========================

def _resolve_current_unit_course(using: str, unit: Unit) -> UnitCourse | None:
    """
    Pick a reasonable UnitCourse (latest year then created_at) for the given unit.
    """
    qs = UnitCourse.objects.using(using).filter(unit=unit).order_by("-year", "-created_at")
    return qs.first()


def import_tutorial_allocations_xlsx(file_like, job, using: str):
    """
    Import Timetable rows (allocations) and attach tutors when possible.
    """
    df = pd.read_excel(file_like)
    col = _validate_headers("tutorial_allocations", df)

    stats = ImportStats()
    log = _create_log(getattr(job.file, "name", "tutorial_allocations.xlsx"), job.created_by)

    total = len(df)
    for i, row in df.iterrows():
        try:
            unit_code = _strip(row[col["unit_code"]])
            day = _as_day_name(_strip(row[col["day_of_week"]]))
            start = _as_time(row[col["start_time"]])
            end = _as_time(row[col["end_time"]])
            room = _strip(row[col["room"]])
            email = _strip(row[col["tutor_email"]]).lower()

            if not unit_code or not day or not start or not end:
                raise ValueError("Missing unit_code/day_of_week/start_time/end_time")

            unit = Unit.objects.using(using).filter(unit_code__iexact=unit_code).first()
            if not unit:
                unit = Unit.objects.filter(unit_code__iexact=unit_code).first()
            if not unit:
                raise ValueError(f"No unit '{unit_code}'")

            uc = _resolve_current_unit_course(using, unit)
            if not uc:
                raise ValueError(f"No UnitCourse found for unit '{unit_code}' in current semester")

            tutor = User.objects.filter(email__iexact=email).first() if email else None

            # Try to find a matching MCT; if not found we still create a Timetable entry
            mct = MasterClassTime.objects.using(using).filter(
                subject_code__iexact=unit_code,
                day_of_week=day,
                start_time=start,
            ).first()

            # Natural key for timetable upsert
            lookup = dict(
                unit_course=uc,
                day_of_week=day,
                start_time=start,
                room=room or "",
            )
            defaults = dict(
                end_time=end,
                start_date=None,
                end_date=None,
                campus=uc.campus if hasattr(uc, "campus") else None,
                master_class=mct,
                tutor_user=tutor,
                updated_at=timezone.now(),
                created_at=timezone.now(),
            )

            Timetable.objects.using(using).update_or_create(
                **lookup, defaults=defaults
            )
            stats.inc()
        except Exception as ex:
            stats.log(f"Row {i + 2}: {ex}")

    _finalise_log(log, stats, total, ok_status="ALLOCATIONS")
    job.rows_ok = stats.ok
    job.rows_error = stats.err
    job.ok = stats.err == 0
    job.finished_at = timezone.now()
    job.save(update_fields=["rows_ok", "rows_error", "ok", "finished_at"])


# =================
# Import dispatcher
# =================

IMPORT_DISPATCH = {
    "eoi": import_eoi_xlsx,
    "master_classes": import_master_classes_xlsx,
    "tutorial_allocations": import_tutorial_allocations_xlsx,
}
