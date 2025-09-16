# imports/services.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Tuple, Dict, Any, Optional, List
from datetime import time, datetime
import re
import uuid

import pandas as pd
from django.apps import apps as django_apps
from django.db import connections, transaction, models
from django.core.exceptions import ValidationError
from django.utils import timezone

from users.models import User
from units.models import Unit, UnitCourse
from timetable.models import MasterClassTime, TimeTable, TimetableImportLog

try:
    from openpyxl import load_workbook
except Exception as e:
    load_workbook = None

# =========================
# Header validation helpers
# =========================
FALLBACK_EOI_TABLE = "eoi_imports"

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

_EOI_SYNONYMS = {
    "unit_code": {"unit_code", "unit", "unitcode", "code"},
    "tutor_email": {"tutor_email", "email", "email_address", "tutoremail"},
    "preference": {"preference", "pref", "rank", "order"},
    "campus": {"campus", "campus_name", "location"},
    "qualifications": {"qualifications", "skills", "technical_skills", "why"},
    "availability": {"availability", "hours", "tutoring_hours"},
}

UNIT_CODE_RX = re.compile(r"\b([A-Z]{3}\d{3})\b")

EMAIL_KEYS = {"email", "email address", "email address*"}
AVAIL_KEYS = {
    "availability",
    "total number of tutoring hours you wish to work - please consider your scholarship / visa condition",
    "total number of tutoring hours you wish to work",
    "total number of tutoring hours",
    "hours",
}
QUAL_KEYS = {
    "what technical and/or other skills do you have for your preferences? and why do you want to teach this unit?",
    "what technical and/or other skills do you have for your preferences? and why?",
    "what technical and/or other skills",
    "skills",
    "why do you want to teach this unit?",
}

CAMPUS_NAMES = {"hobart", "launceston", "online"}

# Flexible header matching (lowercased, spaces collapsed)
def _norm(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip().lower()

def _norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.strip().lower())

def _best_mapping(model) -> Optional[dict]:
    """
    Try to map model fields to our canonical keys using synonyms.
    Returns a mapping like {"unit_code": "unit", "tutor_email": "email", ...}
    or None if the model can't support the required data.
    """
    # collect concrete field names on the model
    all_fields = []
    for f in model._meta.get_fields():
        # only concrete, non-M2M fields with a column
        if getattr(f, "concrete", False) and getattr(f, "attname", None) and not getattr(f, "many_to_many", False):
            all_fields.append(f.attname)

    norm_fields = {_norm_name(n): n for n in all_fields}  # norm->actual

    mapping = {}
    missing_hard = []
    for canon_key, syns in _EOI_SYNONYMS.items():
        found = None
        for syn in syns:
            if _norm_name(syn) in norm_fields:
                found = norm_fields[_norm_name(syn)]
                break
        if found:
            mapping[canon_key] = found
        else:
            # We consider unit_code, tutor_email, campus as hard requirements for a model target
            if canon_key in {"unit_code", "tutor_email", "campus"}:
                missing_hard.append(canon_key)
    if missing_hard:
        return None

    # soft fields get defaults later if absent
    return mapping

def _find_eoi_destination(using: str):
    try:
        app_cfg = django_apps.get_app_config("eoi")
    except LookupError:
        return None, None

    for model in app_cfg.get_models():
        if not _model_has_auto_pk(model):
            continue  # avoid tables that will demand explicit PK values
        mapping = _best_mapping(model)
        if mapping:
            return model, mapping
    return None, None

# --- ensure/fix master_eoi DDL ----------------------------------------------

def _existing_columns(using: str, table: str) -> list[tuple]:
    # returns DESCRIBE rows: (Field, Type, Null, Key, Default, Extra)
    with connections[using].cursor() as c:
        c.execute(f"SHOW COLUMNS FROM `{table}`;")
        return list(c.fetchall())

def _ensure_fallback_eoi_table(using: str):
    ddl = f"""
    CREATE TABLE IF NOT EXISTS `{FALLBACK_EOI_TABLE}` (
        `id` INT NOT NULL AUTO_INCREMENT,
        `unit_code` VARCHAR(32) NOT NULL,
        `tutor_email` VARCHAR(255) NOT NULL,
        `preference` INT NOT NULL DEFAULT 0,
        `campus` VARCHAR(32) NOT NULL,
        `qualifications` TEXT NULL,
        `availability` TEXT NULL,
        PRIMARY KEY (`id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    with connections[using].cursor() as c:
        c.execute(ddl)

def _ensure_master_eoi_table(using: str):
    ddl = """
    CREATE TABLE IF NOT EXISTS `master_eoi` (
      `id` INT NOT NULL AUTO_INCREMENT,
      `unit_code` VARCHAR(32) NOT NULL,
      `tutor_email` VARCHAR(255) NOT NULL,
      `preference` INT DEFAULT 0,
      `campus` VARCHAR(64) NOT NULL,
      `qualifications` LONGTEXT,
      `availability` VARCHAR(128),
      PRIMARY KEY (`id`),
      KEY `idx_eoi_unit` (`unit_code`),
      KEY `idx_eoi_email` (`tutor_email`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
    """
    # DDL must NOT be inside an atomic block
    with connections[using].cursor() as c:
        c.execute(ddl)

def _ensure_master_eoi_columns(using: str):
    # add any missing non-PK columns on older schemas
    wanted = {
        "unit_code": "VARCHAR(32) NOT NULL",
        "tutor_email": "VARCHAR(255) NOT NULL",
        "preference": "INT DEFAULT 0",
        "campus": "VARCHAR(64) NOT NULL",
        "qualifications": "LONGTEXT",
        "availability": "VARCHAR(128)",
    }
    existing = {row[0] for row in _existing_columns(using, "master_eoi")}
    missing = [col for col in wanted if col not in existing]
    if not missing:
        return
    with connections[using].cursor() as c:
        for col in missing:
            c.execute(f"ALTER TABLE `master_eoi` ADD COLUMN `{col}` {wanted[col]};")

def _ensure_master_eoi_pk_auto(using: str):
    """
    Ensure the primary key column is AUTO_INCREMENT, even on legacy schemas
    where the PK is named `master_eoi_id` (or something else) and lacks AUTO_INCREMENT.
    """
    rows = _existing_columns(using, "master_eoi")
    # rows: (Field, Type, Null, Key, Default, Extra)
    pk_name = None
    pk_extra = ""
    for f, t, n, k, d, x in rows:
        if k == "PRI":
            pk_name, pk_extra = f, x or ""
            break

    with connections[using].cursor() as c:
        if not pk_name:
            # no PK at all -> add an auto id
            c.execute("ALTER TABLE `master_eoi` ADD COLUMN `id` INT NOT NULL AUTO_INCREMENT PRIMARY KEY;")
            return

        if "auto_increment" not in pk_extra.lower():
            # make existing PK auto-increment (assume integer-like)
            c.execute(f"ALTER TABLE `master_eoi` MODIFY COLUMN `{pk_name}` INT NOT NULL AUTO_INCREMENT;")

def _find_unit_code(ws) -> Optional[str]:
    # Prefer sheet title first
    m = UNIT_CODE_RX.search(ws.title or "")
    if m:
        return m.group(1)
    # Then search first 8 rows
    for r in ws.iter_rows(min_row=1, max_row=8, values_only=True):
        for v in r:
            m = UNIT_CODE_RX.search(str(v or ""))
            if m:
                return m.group(1)
    return None

def _detect_campus_row(values):
    """
    Accepts rows that contain the campus name ANYWHERE on the row,
    including banner rows like 'Select Tutor with preference number HOBART'.
    Returns the pretty campus token ('Hobart','Launceston','Online') or None.
    """
    tokens = [str(v or "").strip() for v in values if str(v or "").strip()]
    if not tokens:
        return None

    # Exact token match first
    for t in tokens:
        n = _norm(t)
        if n in CAMPUS_NAMES:
            return t.strip().title()

    # Fuzzy: campus embedded in a longer sentence
    joined = " ".join(tokens).lower()
    for name in CAMPUS_NAMES:
        if name in joined:
            return name.title()

    return None

def _find_header(ws, start_row: int) -> Optional[Dict[int, str]]:
    """
    Scan down from start_row to find the row that contains 'Email' etc.
    Some templates have one or two preheader rows; look a bit farther.
    """
    # look up to 12 rows below the campus banner
    for r in range(start_row, min(ws.max_row, start_row + 12)):
        row = [ws.cell(r, c).value for c in range(1, ws.max_column + 1)]
        normed = [_norm(v) for v in row]
        if any(k in normed for k in (_norm("Email Address"), "email", "email address*")):
            return {c: normed[c - 1] for c in range(1, len(normed) + 1)}
    return None

def _col_index(header_map: Dict[int, str], keys: Iterable[str]) -> Optional[int]:
    target = {_norm(k) for k in keys}
    for c, name in header_map.items():
        if name in target:
            return c
    # Heuristic partial matches
    for c, name in header_map.items():
        if any(_norm(k) in name for k in keys):
            return c
    return None

def _iter_normalized_rows(ws) -> Iterable[Dict[str, Any]]:
    """
    Yields dicts with keys:
      unit_code, campus, tutor_email, preference, availability, qualifications
    """
    unit_code = _find_unit_code(ws)
    current_campus = None
    r = 1
    while r <= ws.max_row:
        row_vals = [ws.cell(r, c).value for c in range(1, ws.max_column + 1)]
        campus_here = _detect_campus_row(row_vals)
        if campus_here:
            current_campus = campus_here
            # Find the table header beneath the campus banner
            header = _find_header(ws, r + 1)
            if not header:
                r += 1
                continue
            c_email = _col_index(header, EMAIL_KEYS)
            c_avail = _col_index(header, AVAIL_KEYS)
            c_qual  = _col_index(header, QUAL_KEYS)

            # Guess a preference column:
            # the first column to the left of "Name"/"Email" with small integers often holds the rank
            possible_pref_cols = [1]
            # find "name" column to try col-1 as pref
            for c, name in header.items():
                if "name" in name:
                    if c > 1:
                        possible_pref_cols.insert(0, c - 1)
            # scan down until the next blank email streak
            rr = r + 1
            while rr <= ws.max_row:
                vals = [ws.cell(rr, c).value for c in range(1, ws.max_column + 1)]
                email = str(vals[c_email - 1]).strip() if c_email else ""
                if not email or "@" not in email:
                    # assume table ended once we hit two empty-email rows in a row
                    # (next campus banner will reset things anyway)
                    # check next row quickly
                    nxt = [ws.cell(rr + 1, c).value for c in range(1, ws.max_column + 1)] if rr + 1 <= ws.max_row else []
                    if not nxt or not any("@" in str(v or "") for v in nxt):
                        break
                    rr += 1
                    continue

                # preference
                pref = None
                for pc in possible_pref_cols:
                    if 1 <= pc <= len(vals):
                        try:
                            x = vals[pc - 1]
                            if x is not None and str(x).strip() != "":
                                pref_num = int(str(x).strip())
                                if 0 <= pref_num <= 99:
                                    pref = pref_num
                                    break
                        except Exception:
                            pass
                # fallback: implicit order
                if pref is None:
                    pref = 0

                availability = (str(vals[c_avail - 1]).strip() if c_avail else "") or ""
                qualifications = (str(vals[c_qual - 1]).strip() if c_qual else "") or ""

                yield {
                    "unit_code": unit_code or "",
                    "campus": current_campus,
                    "tutor_email": email.lower(),
                    "preference": pref,
                    "availability": availability,
                    "qualifications": qualifications,
                }
                rr += 1
            # continue scanning after this table
            r = rr
            continue

        r += 1

def _normalize_workbook_to_rows(fobj) -> List[Dict[str, Any]]:
    if load_workbook is None:
        raise ValidationError("openpyxl is not installed on the server.")
    wb = load_workbook(fobj, data_only=True, read_only=True)
    rows: List[Dict[str, Any]] = []
    for ws in wb.worksheets:
        for rec in _iter_normalized_rows(ws):
            # skip obviously broken rows
            if not rec.get("tutor_email") or "@" not in rec["tutor_email"]:
                continue
            if not rec.get("unit_code"):
                continue
            rows.append(rec)
    if not rows:
        raise ValidationError(
            "Could not find any EOI rows. Ensure each unit tab contains a campus section "
            "with an 'Email Address' column. Hidden columns are supported."
        )
    return rows

def _find_eoi_model() -> Optional[Any]:
    try:
        app_cfg = django_apps.get_app_config("eoi")
    except LookupError:
        return None
    needed = {"unit_code", "tutor_email", "preference", "campus", "qualifications", "availability"}
    for model in app_cfg.get_models():
        fields = {f.name for f in model._meta.get_fields() if getattr(f, "attname", None)}
        if needed.issubset(fields):
            return model
    return None

def _table_has_columns(using: str, table: str, cols: Iterable[str]) -> bool:
    cols = list(cols)
    with connections[using].cursor() as c:
        try:
            c.execute(f"SHOW COLUMNS FROM `{table}`;")
            have = {row[0] for row in c.fetchall()}
            return set(cols).issubset(have)
        except Exception:
            return False

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

def _model_has_auto_pk(model) -> bool:
    pk = model._meta.pk
    return isinstance(pk, (models.AutoField, models.BigAutoField, models.SmallAutoField))
# ==================
# Logging to control
# ==================

@dataclass
class ImportStats:
    ok: int = 0
    err: int = 0
    errors: list[str] = field(default_factory=list)

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

def import_eoi_excel(fileobj, job, using: str):
    """
    Parse the Casual Master EOI Spreadsheet and write rows directly into eoi.EoiApp,
    creating Units/Campuses/Users as needed in the current semester DB.
    """
    rows = _normalize_workbook_to_rows(fileobj)
    # If the normalizer could not parse, the earlier fallback (pandas) in _normalize_workbook_to_rows will have populated rows.
    if not rows:
        raise ValidationError("No EOI rows parsed from the workbook.")

    from eoi.models import EoiApp
    from units.models import Unit
    from users.models import Campus, User

    # campus synonym map
    CAMPUS_MAP = {
        "hobart": "SB",
        "sandy bay": "SB",
        "launceston": "IR",
        "inveresk": "IR",
        "online": "ONLINE",
        "distance": "ONLINE",
    }

    created = 0
    updated = 0
    with transaction.atomic(using=using):
        for r in rows:
            unit_code = (r.get("unit_code") or "").strip().upper()
            if not unit_code:
                continue
            # ensure unit
            unit, _ = Unit.objects.using(using).get_or_create(
                unit_code=unit_code,
                defaults={"unit_name": unit_code}
            )
            # campus
            campus_txt = (r.get("campus") or "").strip()
            campus_key = CAMPUS_MAP.get(campus_txt.lower(), None)
            campus = None
            if campus_key:
                campus, _ = Campus.objects.using(using).get_or_create(
                    campus_name=campus_key,
                    defaults={"campus_location": campus_txt or campus_key}
                )
            # user
            email = (r.get("tutor_email") or "").strip().lower()
            if not email or "@" not in email:
                continue
            # Try to split name from extras
            tutor_name = ""
            extras = r.get("_extra") or {}
            if extras:
                tutor_name = (extras.get("tutor_name") or "").strip()
            first, last = "", ""
            if tutor_name:
                parts = tutor_name.split()
                first = parts[0]
                last = " ".join(parts[1:]) if len(parts) > 1 else ""
            user, _ = User.objects.using(using).get_or_create(
                email=email,
                defaults={"first_name": first, "last_name": last, "is_active": False}
            )
            # upsert EoiApp (SCD handled by model .save())
            obj, created_flag = EoiApp.objects.using(using).get_or_create(
                applicant_user=user,
                unit=unit,
                campus=campus,
                defaults={
                    "status": "Submitted",
                    "remarks": "",
                    "preference": int(r.get("preference") or 0),
                    "qualifications": r.get("qualifications") or "",
                    "availability": r.get("availability") or "",
                    "tutor_email": email,
                    "tutor_name": tutor_name,
                    "tutor_current": extras.get("eoi_status_text") or "",
                    "location_text": extras.get("location_text") or campus_txt or "",
                    "gpa": (float(extras.get("gpa")) if str(extras.get("gpa") or "").strip() not in {"", "nan"} else None),
                    "supervisor": extras.get("supervisor") or "",
                    "applied_units": extras.get("applied_units") or None,
                    "tutoring_experience": extras.get("tutoring_experience") or "",
                    "hours_available": (int(extras.get("hours_available")) if str(extras.get("hours_available") or "").strip().isdigit() else None),
                    "scholarship_received": None if (extras.get("scholarship_received") is None) else str(extras.get("scholarship_received")).strip().lower() in {"y", "yes", "true", "1"},
                    "transcript_link": extras.get("transcript_link") or "",
                    "cv_link": extras.get("cv_link") or "",
                }
            )
            if not created_flag:
                # update mutable fields and save to trigger SCD if changed
                obj.preference = int(r.get("preference") or obj.preference or 0)
                obj.qualifications = r.get("qualifications") or obj.qualifications or ""
                obj.availability = r.get("availability") or obj.availability or ""
                # extras
                if tutor_name:
                    obj.tutor_name = tutor_name
                ex = extras
                if ex:
                    if ex.get("eoi_status_text"): obj.tutor_current = ex["eoi_status_text"]
                    if ex.get("location_text"): obj.location_text = ex["location_text"]
                    try:
                        g = ex.get("gpa"); obj.gpa = float(g) if str(g or "").strip() not in {"", "nan"} else obj.gpa
                    except Exception: pass
                    if ex.get("supervisor"): obj.supervisor = ex["supervisor"]
                    if ex.get("applied_units"): obj.applied_units = ex["applied_units"]
                    if ex.get("tutoring_experience"): obj.tutoring_experience = ex["tutoring_experience"]
                    try:
                        h = ex.get("hours_available"); obj.hours_available = int(h) if str(h or "").strip().isdigit() else obj.hours_available
                    except Exception: pass
                    if ex.get("scholarship_received") is not None:
                        v = str(ex["scholarship_received"]).strip().lower()
                        obj.scholarship_received = True if v in {"y","yes","true","1"} else False if v in {"n","no","false","0"} else obj.scholarship_received
                    if ex.get("transcript_link"): obj.transcript_link = ex["transcript_link"]
                    if ex.get("cv_link"): obj.cv_link = ex["cv_link"]
                obj.save()
                updated += 1
            else:
                created += 1

    return {
        "result": "ok",
        "target": "eoi_app",
        "inserted": created,
        "updated": updated,
    }

    # Fallback: make sure `master_eoi` exists, then insert via SQL
    _ensure_master_eoi_table(using)       # DDL (no atomic)
    _ensure_master_eoi_columns(using)     # DDL (no atomic)
    _ensure_master_eoi_pk_auto(using)     # DDL (no atomic)
    _ensure_fallback_eoi_table(using)
    with connections[using].cursor() as c, transaction.atomic(using=using):
        sql = (
            f"INSERT INTO `{FALLBACK_EOI_TABLE}` "
            "(`unit_code`,`tutor_email`,`preference`,`campus`,`qualifications`,`availability`) "
            "VALUES (%s,%s,%s,%s,%s,%s)"
        )
        params = [
            (
                r["unit_code"],
                r["tutor_email"].lower(),
                int(r.get("preference") or 0),
                r["campus"],
                r.get("qualifications", ""),
                r.get("availability", ""),
            )
            for r in rows
        ]
        c.executemany(sql, params)
    return {"inserted": len(params), "table": FALLBACK_EOI_TABLE}

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

            TimeTable.objects.using(using).update_or_create(
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

# ==================
# TUTOR ALLOCATION
# ==================

# ---------- utility ----------

def _apps_get(app_label: str, model_name: str):
    return django_apps.get_model(app_label, model_name)


def _strip(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _to_int(value: Any) -> Optional[int]:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(str(value).strip())
    except Exception:
        return None


def _to_time(x: Any) -> Optional[time]:
    """
    Excel times can arrive as:
      - Python datetime.time (already OK)
      - datetime.datetime with a date (take .time())
      - number (Excel time fraction of a day)
      - string ("13:00", "1:00 PM")
    """
    if x is None or x == "":
        return None
    if isinstance(x, time):
        return x
    if isinstance(x, datetime):
        return x.time()
    # numeric excel time fraction
    if isinstance(x, (int, float)):
        seconds = float(x) * 24 * 60 * 60
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return time(h, m, s)
    # string
    s = str(x).strip()
    # "1:23 PM"/"13:23"
    try:
        for fmt in ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M:%S %p"):
            try:
                return datetime.strptime(s, fmt).time()
            except Exception:
                pass
    except Exception:
        pass
    return None


# ---------- models via apps registry (avoids hard imports & circulars) ----------

EOIImport = _apps_get("imports", "EOIImport")                     # staging log (your existing table)
MasterEOI = _apps_get("eoi", "MasterEOI")                         # normalized EOI rows
MasterClassTime = _apps_get("eoi", "MasterClassTime")             # normalized timeslots for every unit class
Campus = _apps_get("users", "Campus")                             # reference data
Unit = _apps_get("units", "Unit")                                 # reference data


# ---------- workbook readers ----------

REQUIRED_EOI_COLS = {
    "unit_code", "tutor_email", "preference", "campus", "qualifications", "availability"
}

EOI_HEADER_ALIASES = {
    "unit_code": {"unit code", "unit", "code"},
    "tutor_email": {"email address", "email", "tutor email"},
    "preference": {"preference", "pref", "rank"},
    "campus": {"campus"},
    "qualifications": {"qualifications", "skills", "notes"},
    "availability": {"availability", "hours", "available hours"},
}

CLASS_HEADER_ALIASES = {
    "unit_code": {"unit code", "unit", "code"},
    "campus": {"campus"},
    "activity": {"activity", "class type", "type"},
    "day": {"day"},
    "start": {"start", "start time", "begin"},
    "end": {"end", "end time", "finish"},
    "group": {"class", "group", "stream", "number"},
}

DAY_NORMALIZE = {
    "mon": "Mon", "monday": "Mon",
    "tue": "Tue", "tues": "Tue", "tuesday": "Tue",
    "wed": "Wed", "wednesday": "Wed",
    "thu": "Thu", "thur": "Thu", "thurs": "Thu", "thursday": "Thu",
    "fri": "Fri", "friday": "Fri",
    "sat": "Sat", "saturday": "Sat",
    "sun": "Sun", "sunday": "Sun",
}


def _best_header_map(header_cells: Iterable[str], aliases: Dict[str, Set[str]]) -> Dict[int, str]:
    """
    Given a row of header strings and a mapping of canonical->aliases,
    return a dict: {column_index: canonical_name}
    """
    header_map: Dict[int, str] = {}
    for idx, raw in enumerate(header_cells):
        label = _strip(raw).lower()
        for canonical, alias_set in aliases.items():
            if label == canonical:
                header_map[idx] = canonical
                break
            if label in alias_set:
                header_map[idx] = canonical
                break
    return header_map


def _normalize_eoi_sheet(ws) -> List[Dict[str, Any]]:
    """
    Scan a unit sheet. We search for the first row that can be interpreted as the header row
    (must cover at least the EOI required columns with aliases), then read down until an empty tutor_email.
    Hidden columns are handled by openpyxl transparently.
    """
    rows: List[Dict[str, Any]] = []

    # collect header row
    header_map: Dict[int, str] = {}
    header_row_idx = None
    for r in ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True):
        header_map = _best_header_map(r, EOI_HEADER_ALIASES)
        have = set(header_map.values())
        if REQUIRED_EOI_COLS.issubset(have):
            header_row_idx = r
            break

    if not header_map:
        return rows

    # read data after the header
    started = False
    for i, r in enumerate(ws.iter_rows(values_only=True)):
        if not started:
            # skip until row equals header_row_idx
            if r is header_row_idx:
                started = True
            continue
        # build row dict
        rec = {k: None for k in REQUIRED_EOI_COLS}
        for c_idx, canonical in header_map.items():
            rec[canonical] = r[c_idx]
        # a valid row must have tutor_email
        if not _strip(rec.get("tutor_email")):
            continue
        rows.append({
            "unit_code": _strip(rec["unit_code"]),
            "tutor_email": _strip(rec["tutor_email"]).lower(),
            "preference": _to_int(rec["preference"]) or 0,
            "campus": _strip(rec["campus"]),
            "qualifications": _strip(rec["qualifications"]),
            "availability": _to_int(rec["availability"]) or 0,
        })
    return rows


def _normalize_workbook_to_eoi_rows(fobj) -> List[Dict[str, Any]]:
    wb = load_workbook(fobj, data_only=True, read_only=True)
    out: List[Dict[str, Any]] = []
    for name in wb.sheetnames:
        ws = wb[name]
        # Skip obvious cover / index sheets
        if re.search(r"(cover|index|instruction|summary)", name, re.I):
            continue
        rows = _normalize_eoi_sheet(ws)
        out.extend(rows)
    if not out:
        raise ValidationError(
            "Could not find any EOI rows. Ensure unit tabs contain a tutor section "
            "with an 'Email Address' column. Hidden columns are supported."
        )
    return out


def _normalize_workbook_to_classes(fobj) -> List[Dict[str, Any]]:
    """
    Master class list parser — flexible header mapping.
    Expected columns (case/alias-insensitive):
        unit_code, campus, activity, day, start, end, [group]
    """
    wb = load_workbook(fobj, data_only=True, read_only=True)
    out: List[Dict[str, Any]] = []

    for name in wb.sheetnames:
        ws = wb[name]
        # find header
        header_map: Dict[int, str] = {}
        header_row = None
        for r in ws.iter_rows(min_row=1, max_row=ws.max_row, values_only=True):
            header_map = _best_header_map(r, CLASS_HEADER_ALIASES)
            if {"unit_code", "day", "start", "end"}.issubset(set(header_map.values())):
                header_row = r
                break
        if not header_map:
            continue

        started = False
        for r in ws.iter_rows(values_only=True):
            if not started:
                if r is header_row:
                    started = True
                continue
            rec = {}
            for c_idx, canonical in header_map.items():
                rec[canonical] = r[c_idx]

            unit_code = _strip(rec.get("unit_code"))
            if not unit_code:
                continue

            day_raw = _strip(rec.get("day")).lower()
            day = DAY_NORMALIZE.get(day_raw, day_raw.capitalize() or None)
            start = _to_time(rec.get("start"))
            end = _to_time(rec.get("end"))
            if not day or not start or not end:
                continue

            out.append({
                "unit_code": unit_code,
                "campus": _strip(rec.get("campus")),
                "activity": _strip(rec.get("activity")) or "Class",
                "group": _strip(rec.get("group")),
                "day": day,
                "start_time": start,
                "end_time": end,
            })

    if not out:
        raise ValidationError("No class rows found in the Master class list workbook.")
    return out


# ---------- reference data upserts ----------

def _ensure_campuses(rows: Iterable[Dict[str, Any]], *, using: str) -> int:
    names = { _strip(r.get("campus")) for r in rows if _strip(r.get("campus")) }
    if not names:
        return 0
    existing = set(
        Campus.objects.using(using)
        .filter(campus_name__in=names)
        .values_list("campus_name", flat=True)
    )
    to_create = [Campus(campus_name=n) for n in (names - existing)]
    if to_create:
        Campus.objects.using(using).bulk_create(to_create, ignore_conflicts=True)
    return len(to_create)


def _ensure_units(rows: Iterable[Dict[str, Any]], *, using: str) -> int:
    codes = { _strip(r.get("unit_code")) for r in rows if _strip(r.get("unit_code")) }
    if not codes:
        return 0
    existing = set(
        Unit.objects.using(using).filter(code__in=codes).values_list("code", flat=True)
    )
    to_create = [Unit(code=c, name=c) for c in (codes - existing)]  # name unknown → use code
    if to_create:
        Unit.objects.using(using).bulk_create(to_create, ignore_conflicts=True)
    return len(to_create)


# ---------- writers ----------

def _write_eoi_staging(rows: List[Dict[str, Any]], *, job, using: str) -> int:
    """Keep your current staging log behaviour (eoi_imports)."""
    objs = [
        EOIImport(
            job=job,
            unit_code=r["unit_code"],
            tutor_email=r["tutor_email"],
            preference=r["preference"],
            campus=r["campus"],
            qualifications=r["qualifications"],
            availability=r["availability"],
        )
        for r in rows
    ]
    if objs:
        EOIImport.objects.using(using).bulk_create(objs)
    return len(objs)


def _upsert_master_eoi(rows: List[Dict[str, Any]], *, using: str) -> Tuple[int, int]:
    """
    Upsert into eoi.MasterEOI by (unit_code, tutor_email).
    Returns (created, updated).
    """
    # First, create any missing pairs
    pairs = {(r["unit_code"], r["tutor_email"]) for r in rows}
    existing_pairs = set(
        MasterEOI.objects.using(using)
        .filter(unit_code__in=[p[0] for p in pairs], tutor_email__in=[p[1] for p in pairs])
        .values_list("unit_code", "tutor_email")
    )
    to_create = []
    for r in rows:
        key = (r["unit_code"], r["tutor_email"])
        if key not in existing_pairs:
            to_create.append(
                MasterEOI(
                    unit_code=r["unit_code"],
                    tutor_email=r["tutor_email"],
                    preference=r["preference"],
                    campus=r["campus"],
                    qualifications=r["qualifications"],
                    availability=r["availability"],
                )
            )
    created = 0
    if to_create:
        MasterEOI.objects.using(using).bulk_create(to_create, ignore_conflicts=True)
        created = len(to_create)

    # Update fields on existing rows
    # (do a second pass to pick only the rows that already exist)
    to_update = []
    existing_qs = MasterEOI.objects.using(using).filter(
        unit_code__in=[p[0] for p in existing_pairs],
        tutor_email__in=[p[1] for p in existing_pairs],
    )
    existing_map: Dict[Tuple[str, str], Any] = {
        (m.unit_code, m.tutor_email): m for m in existing_qs
    }
    for r in rows:
        key = (r["unit_code"], r["tutor_email"])
        m = existing_map.get(key)
        if not m:
            continue
        dirty = False
        if m.preference != (r["preference"] or 0):
            m.preference = r["preference"] or 0
            dirty = True
        if m.campus != r["campus"]:
            m.campus = r["campus"]
            dirty = True
        if m.qualifications != r["qualifications"]:
            m.qualifications = r["qualifications"]
            dirty = True
        if m.availability != (r["availability"] or 0):
            m.availability = r["availability"] or 0
            dirty = True
        if dirty:
            to_update.append(m)

    updated = 0
    if to_update:
        MasterEOI.objects.using(using).bulk_update(
            to_update, ["preference", "campus", "qualifications", "availability"]
        )
        updated = len(to_update)

    return created, updated


def _write_master_classes(rows: List[Dict[str, Any]], *, using: str) -> int:
    """
    Insert all class rows into MasterClassTime.
    We don't try to deduplicate here (coordinators may re-upload new terms);
    if you want deduplication, add a unique_together in the model.
    """
    objs = [
        MasterClassTime(
            unit_code=r["unit_code"],
            campus=r["campus"],
            activity=r["activity"],
            class_group=r["group"],
            day=r["day"],
            start_time=r["start_time"],
            end_time=r["end_time"],
        )
        for r in rows
    ]
    if objs:
        MasterClassTime.objects.using(using).bulk_create(objs)
    return len(objs)


# ---------- public import API (used by the view) ----------

def import_eoi_excel(fileobj, job, using: str):
    """
    Parse the Casual Master EOI Spreadsheet and write rows directly into eoi.EoiApp,
    creating Units/Campuses/Users as needed in the current semester DB.
    """
    rows = _normalize_workbook_to_rows(fileobj)
    # If the normalizer could not parse, the earlier fallback (pandas) in _normalize_workbook_to_rows will have populated rows.
    if not rows:
        raise ValidationError("No EOI rows parsed from the workbook.")

    from eoi.models import EoiApp
    from units.models import Unit
    from users.models import Campus, User

    # campus synonym map
    CAMPUS_MAP = {
        "hobart": "SB",
        "sandy bay": "SB",
        "launceston": "IR",
        "inveresk": "IR",
        "online": "ONLINE",
        "distance": "ONLINE",
    }

    created = 0
    updated = 0
    with transaction.atomic(using=using):
        for r in rows:
            unit_code = (r.get("unit_code") or "").strip().upper()
            if not unit_code:
                continue
            # ensure unit
            unit, _ = Unit.objects.using(using).get_or_create(
                unit_code=unit_code,
                defaults={"unit_name": unit_code}
            )
            # campus
            campus_txt = (r.get("campus") or "").strip()
            campus_key = CAMPUS_MAP.get(campus_txt.lower(), None)
            campus = None
            if campus_key:
                campus, _ = Campus.objects.using(using).get_or_create(
                    campus_name=campus_key,
                    defaults={"campus_location": campus_txt or campus_key}
                )
            # user
            email = (r.get("tutor_email") or "").strip().lower()
            if not email or "@" not in email:
                continue
            # Try to split name from extras
            tutor_name = ""
            extras = r.get("_extra") or {}
            if extras:
                tutor_name = (extras.get("tutor_name") or "").strip()
            first, last = "", ""
            if tutor_name:
                parts = tutor_name.split()
                first = parts[0]
                last = " ".join(parts[1:]) if len(parts) > 1 else ""
            user, _ = User.objects.using(using).get_or_create(
                email=email,
                defaults={"first_name": first, "last_name": last, "is_active": False}
            )
            # upsert EoiApp (SCD handled by model .save())
            obj, created_flag = EoiApp.objects.using(using).get_or_create(
                applicant_user=user,
                unit=unit,
                campus=campus,
                defaults={
                    "status": "Submitted",
                    "remarks": "",
                    "preference": int(r.get("preference") or 0),
                    "qualifications": r.get("qualifications") or "",
                    "availability": r.get("availability") or "",
                    "tutor_email": email,
                    "tutor_name": tutor_name,
                    "tutor_current": extras.get("eoi_status_text") or "",
                    "location_text": extras.get("location_text") or campus_txt or "",
                    "gpa": (float(extras.get("gpa")) if str(extras.get("gpa") or "").strip() not in {"", "nan"} else None),
                    "supervisor": extras.get("supervisor") or "",
                    "applied_units": extras.get("applied_units") or None,
                    "tutoring_experience": extras.get("tutoring_experience") or "",
                    "hours_available": (int(extras.get("hours_available")) if str(extras.get("hours_available") or "").strip().isdigit() else None),
                    "scholarship_received": None if (extras.get("scholarship_received") is None) else str(extras.get("scholarship_received")).strip().lower() in {"y", "yes", "true", "1"},
                    "transcript_link": extras.get("transcript_link") or "",
                    "cv_link": extras.get("cv_link") or "",
                }
            )
            if not created_flag:
                # update mutable fields and save to trigger SCD if changed
                obj.preference = int(r.get("preference") or obj.preference or 0)
                obj.qualifications = r.get("qualifications") or obj.qualifications or ""
                obj.availability = r.get("availability") or obj.availability or ""
                # extras
                if tutor_name:
                    obj.tutor_name = tutor_name
                ex = extras
                if ex:
                    if ex.get("eoi_status_text"): obj.tutor_current = ex["eoi_status_text"]
                    if ex.get("location_text"): obj.location_text = ex["location_text"]
                    try:
                        g = ex.get("gpa"); obj.gpa = float(g) if str(g or "").strip() not in {"", "nan"} else obj.gpa
                    except Exception: pass
                    if ex.get("supervisor"): obj.supervisor = ex["supervisor"]
                    if ex.get("applied_units"): obj.applied_units = ex["applied_units"]
                    if ex.get("tutoring_experience"): obj.tutoring_experience = ex["tutoring_experience"]
                    try:
                        h = ex.get("hours_available"); obj.hours_available = int(h) if str(h or "").strip().isdigit() else obj.hours_available
                    except Exception: pass
                    if ex.get("scholarship_received") is not None:
                        v = str(ex["scholarship_received"]).strip().lower()
                        obj.scholarship_received = True if v in {"y","yes","true","1"} else False if v in {"n","no","false","0"} else obj.scholarship_received
                    if ex.get("transcript_link"): obj.transcript_link = ex["transcript_link"]
                    if ex.get("cv_link"): obj.cv_link = ex["cv_link"]
                obj.save()
                updated += 1
            else:
                created += 1

    return {
        "result": "ok",
        "target": "eoi_app",
        "inserted": created,
        "updated": updated,
    }


def import_master_class_list(fileobj, job, *, using: str) -> Dict[str, Any]:
    """
    Parse the 'Master class list' workbook and populate MasterClassTime.
    Also make sure Units & Campuses referenced here exist.
    """
    rows = _normalize_workbook_to_classes(fileobj)
    with transaction.atomic(using=using):
        campus_new = _ensure_campuses(rows, using=using)
        unit_new = _ensure_units(rows, using=using)
        inserted = _write_master_classes(rows, using=using)

    return {
        "result": "ok",
        "target": "master_class_time",
        "inserted": inserted,
        "created_campuses": campus_new,
        "created_units": unit_new,
    }

# =================
# Import dispatcher
# =================

IMPORT_DISPATCH = {
    "eoi": import_eoi_excel,
    "master_class_list": import_master_classes_xlsx,
    "master_classes": import_master_classes_xlsx,
    "tutorial_allocations": import_tutorial_allocations_xlsx,
}

