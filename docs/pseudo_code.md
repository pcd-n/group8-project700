# https://github.com/pcd-n/group8-project700
#--------------------------------------------------------------------------#
0) Shared helpers
FUNCTION assert_role(user_id, allowed_roles):
    roles = SELECT r.role_name
            FROM "UserRoles" ur JOIN "Role" r ON ur.role_id = r.role_id
            WHERE ur.user_id = user_id
    IF not any(role IN allowed_roles for role in roles):
        RAISE "ACCESS_DENIED"

FUNCTION audit_log(action, actor_user_id, target, metadata_json):
    // app-side immutable log

FUNCTION notify(user_id, message, payload_json):
    // email notification


#--------------------------------------------------------------------------#
1) Admin lane (EOI import + full control of allocations)
FUNCTION admin_upload_eoi(admin_user_id, file):
    assert_role(admin_user_id, ["ADMIN"])
    rows = parse(file)  // columns mapped to EoiApp fields

    FOR EACH r IN rows:
        IF empty(r.applicant_user_id) OR empty(r.campus_id) OR empty(r.status) OR empty(r.valid_from):
            audit_log("EOI_FLAGGED_INCOMPLETE", admin_user_id, {applicant_user_id:r.applicant_user_id}, {})
            CONTINUE

        dup_exists = EXISTS(
          SELECT 1 FROM "EoiApp"
          WHERE applicant_user_id = r.applicant_user_id
            AND COALESCE(unit_id,-1) = COALESCE(r.unit_id,-1)
            AND campus_id = r.campus_id
            AND is_current = TRUE
        )
        IF dup_exists:
            audit_log("EOI_FLAGGED_DUPLICATE", admin_user_id, {applicant_user_id:r.applicant_user_id, unit_id:r.unit_id, campus_id:r.campus_id}, {})
            CONTINUE

        INSERT INTO "EoiApp"(eoi_app_id, applicant_user_id, unit_id, campus_id,
                              status, remarks, valid_from, valid_to, is_current, version)
        VALUES (UUID_GENERATE(), r.applicant_user_id, r.unit_id, r.campus_id,
                r.status, r.remarks, r.valid_from, r.valid_to, TRUE, 1)

        audit_log("EOI_STORED", admin_user_id, {applicant_user_id:r.applicant_user_id, unit_id:r.unit_id, campus_id:r.campus_id}, {})

FUNCTION admin_allocate_to_class(admin_user_id, tutor_user_id, unit_course_id, campus_id, slot, allow_override):
    assert_role(admin_user_id, ["ADMIN"])
    audit_log("ALLOCATION_ATTEMPTED", admin_user_id, {tutor_user_id, unit_course_id}, {slot})

    result = clash_check_on_allocation(tutor_user_id, unit_course_id, campus_id, slot)
    IF result.clash == TRUE AND allow_override != TRUE:
        RETURN {status:"NEEDS_ADJUSTMENT", reason:result.reason}

    upsert_timetable_assignment(unit_course_id, campus_id, slot, tutor_user_id)

    IF result.clash == TRUE AND allow_override == TRUE:
        audit_log("OVERRIDE_ACCEPTED", admin_user_id, {tutor_user_id, unit_course_id}, {reason:result.reason})

    audit_log("ALLOCATED", admin_user_id, {tutor_user_id, unit_course_id}, {})
    RETURN {status:"ALLOCATED"}

FUNCTION admin_remove_allocation(admin_user_id, unit_course_id, campus_id, slot):
    assert_role(admin_user_id, ["ADMIN"])
    // Remove tutor assignment for the exact class slot
    existing = SELECT timetable_id FROM "TimeTable"
               WHERE unit_course_id=unit_course_id AND campus_id=campus_id
                 AND day_of_week=slot.day_of_week
                 AND start_time=slot.start_time AND end_time=slot.end_time
                 AND COALESCE(start_date,'0001-01-01') = COALESCE(slot.start_date,'0001-01-01')
                 AND COALESCE(end_date,  '0001-01-01') = COALESCE(slot.end_date,  '0001-01-01')

    IF existing:
        UPDATE "TimeTable"
           SET tutor_user_id = NULL, updated_at = now()
         WHERE timetable_id = existing.timetable_id
        audit_log("ALLOCATION_REMOVED", admin_user_id, {unit_course_id}, {slot})
        RETURN {status:"REMOVED"}
    ELSE:
        RETURN {status:"NO_MATCH"}

FUNCTION admin_change_allocation(admin_user_id, from_tutor_user_id, to_tutor_user_id, unit_course_id, campus_id, slot, allow_override):
    assert_role(admin_user_id, ["ADMIN"])
    // 1) Remove current tutor (if any) for the slot
    admin_remove_allocation(admin_user_id, unit_course_id, campus_id, slot)

    // 2) Allocate new tutor to the same slot
    RETURN admin_allocate_to_class(admin_user_id, to_tutor_user_id, unit_course_id, campus_id, slot, allow_override)

FUNCTION admin_check_unit_status(admin_user_id, unit_id, term, year, campus_id):
    assert_role(admin_user_id, ["ADMIN"])
    row = SELECT status FROM "UnitCourses"
          WHERE unit_id=unit_id AND term=term AND year=year AND campus_id=campus_id
    RETURN row.status


#--------------------------------------------------------------------------#
2) Unit Coordinator lane (candidate filtering, preference, allocation, publish)
FUNCTION uc_filter_candidates(uc_user_id, unit_id, campus_id, term, year, filters):
    assert_role(uc_user_id, ["UNIT_COORDINATOR"])
    RETURN SELECT ea.eoi_app_id, ea.applicant_user_id, u.first_name, u.last_name, u.email,
                  ea.status, ea.remarks
           FROM "EoiApp" ea
           JOIN "Users" u ON u.user_id = ea.applicant_user_id
           WHERE ea.is_current = TRUE
             AND ea.unit_id = unit_id
             AND ea.campus_id = campus_id
             APPLY(filters)

FUNCTION uc_preference_shortlist(uc_user_id, preferences):
    assert_role(uc_user_id, ["UNIT_COORDINATOR"])
    // preferences: [{eoi_app_id, status_label, notes}]
    FOR EACH r IN preferences:
        UPDATE "EoiApp"
           SET status = r.status_label, remarks = r.notes, updated_at = now()
         WHERE eoi_app_id = r.eoi_app_id AND is_current = TRUE
    audit_log("PREFERENCES_SAVED", uc_user_id, {count: len(preferences)}, {})

FUNCTION uc_allocate_to_class(uc_user_id, tutor_user_id, unit_course_id, campus_id, slot, allow_override):
    assert_role(uc_user_id, ["UNIT_COORDINATOR"])
    audit_log("ALLOCATION_ATTEMPTED", uc_user_id, {tutor_user_id, unit_course_id}, {slot})

    result = clash_check_on_allocation(tutor_user_id, unit_course_id, campus_id, slot)
    IF result.clash == TRUE AND allow_override != TRUE:
        RETURN {status:"NEEDS_ADJUSTMENT", reason:result.reason}

    upsert_timetable_assignment(unit_course_id, campus_id, slot, tutor_user_id)

    IF result.clash == TRUE AND allow_override == TRUE:
        audit_log("OVERRIDE_ACCEPTED", uc_user_id, {tutor_user_id, unit_course_id}, {reason:result.reason})

    audit_log("ALLOCATED", uc_user_id, {tutor_user_id, unit_course_id}, {})
    RETURN {status:"ALLOCATED"}

FUNCTION uc_decide_publish(uc_user_id, unit_id, term, year, campus_id, decision):
    assert_role(uc_user_id, ["UNIT_COORDINATOR"])
    IF decision == "APPROVED":
        write_and_publish(unit_id, term, year, campus_id, uc_user_id)
        RETURN {status:"PUBLISHED"}
    ELSE:
        audit_log("PUBLISH_REJECTED", uc_user_id, {unit_id, term, year, campus_id}, {})
        RETURN {status:"ADJUST_REQUIRED"}


#--------------------------------------------------------------------------#
3) Tutor lane (view‑only)
FUNCTION tutor_view_published_timetable(tutor_user_id, term, year, campus_id):
    assert_role(tutor_user_id, ["TUTOR"])
    RETURN SELECT tt.timetable_id, uc.unit_id, tt.day_of_week, tt.start_time, tt.end_time, tt.room
           FROM "TimeTable" tt
           JOIN "UnitCourses" uc ON tt.unit_course_id = uc.unit_course_id
           WHERE tt.tutor_user_id = tutor_user_id
             AND uc.term = term AND uc.year = year
             AND tt.campus_id = campus_id
             AND (SELECT status FROM "UnitCourses"
                  WHERE unit_course_id = uc.unit_course_id) = 'Published'

#--------------------------------------------------------------------------#
4) System services (shared)
FUNCTION provide_filter_search_ui(user_id, criteria):
    assert_role(user_id, ["ADMIN","UNIT_COORDINATOR"])
    // Base from EoiApp and add AND filters with exact column names
    // (same as uc_filter_candidates for UCs; Admin can search across units/campuses)

FUNCTION clash_check_on_allocation(tutor_user_id, unit_course_id, campus_id, slot):
    overlap = EXISTS(
      SELECT 1 FROM "TimeTable"
      WHERE tutor_user_id = tutor_user_id
        AND campus_id = campus_id
        AND day_of_week = slot.day_of_week
        AND time_ranges_overlap(start_time, end_time, slot.start_time, slot.end_time)
        AND date_ranges_overlap(start_date, end_date, slot.start_date, slot.end_date)
    )
    IF overlap: RETURN {clash: TRUE, reason: "Existing allocation overlap"}

    RETURN {clash: FALSE}

FUNCTION write_and_publish(unit_id, term, year, campus_id, actor_user_id):
    has_rows = EXISTS(
      SELECT 1 FROM "TimeTable"
      WHERE unit_course_id IN (
        SELECT unit_course_id FROM "UnitCourses"
        WHERE unit_id=unit_id AND term=term AND year=year AND campus_id=campus_id
      )
      AND tutor_user_id IS NOT NULL
    )
    IF NOT has_rows:
        RETURN {status:"BLOCKED", reason:"No allocations to publish"}

    UPDATE "UnitCourses"
       SET status = 'Published', updated_at = now()
     WHERE unit_id = unit_id AND term = term AND year = year AND campus_id = campus_id

    audit_log("PUBLISH_APPROVED", actor_user_id, {unit_id, term, year, campus_id}, {})

    affected_tutors = SELECT DISTINCT tt.tutor_user_id
                      FROM "TimeTable" tt
                      JOIN "UnitCourses" uc ON uc.unit_course_id = tt.unit_course_id
                      WHERE uc.unit_id = unit_id AND uc.term = term AND uc.year = year
                        AND uc.campus_id = campus_id
                        AND tt.tutor_user_id IS NOT NULL

    FOR EACH t IN affected_tutors:
        notify(t, "Your teaching schedule is published", {unit_id, term, year, campus_id})
        audit_log("TUTOR_NOTIFIED", actor_user_id, {tutor_user_id:t}, {unit_id, term, year, campus_id})


FUNCTION upsert_timetable_assignment(unit_course_id, campus_id, slot, tutor_user_id):
    existing = SELECT timetable_id FROM "TimeTable"
               WHERE unit_course_id = unit_course_id
                 AND campus_id = campus_id
                 AND day_of_week = slot.day_of_week
                 AND start_time = slot.start_time
                 AND end_time   = slot.end_time
                 AND COALESCE(start_date,'0001-01-01') = COALESCE(slot.start_date,'0001-01-01')
                 AND COALESCE(end_date,  '0001-01-01') = COALESCE(slot.end_date,  '0001-01-01')

    IF existing:
        UPDATE "TimeTable"
           SET tutor_user_id = tutor_user_id, room = COALESCE(slot.room, room), updated_at = now()
         WHERE timetable_id = existing.timetable_id
    ELSE:
        INSERT INTO "TimeTable"(unit_course_id, campus_id, room, day_of_week,
                                start_time, end_time, start_date, end_date, tutor_user_id)
        VALUES (unit_course_id, campus_id, slot.room, slot.day_of_week,
                slot.start_time, slot.end_time, slot.start_date, slot.end_date, tutor_user_id)
