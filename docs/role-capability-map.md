# Role Capability Map: Backend vs Frontend

This document maps the role capabilities exposed by backend routes and compares them with the HTML frontend entry points and templates.

## Admin

### Backend capabilities
- Manage users: list users, activate/deactivate, change roles (`/admin/users*`).
- Manage courses: create, reassign lecturer, delete (`/admin/courses/*`).
- Manage enrollments: enroll/unenroll students (`/admin/enrollments*`).
- View audit logs (`/admin/audit-logs`, `/admin/`).
- API management routes for courses and exams also allow admin actions (`/courses/*`, `/exams/*`).

### Frontend status (before fixes)
- Admin dashboard template supports user/course/enrollment management (`templates/admin/dashboard.html`).
- Login flow redirected all non-students to `/dashboard/` (lecturer dashboard), which made admin-first flow inconsistent and hid admin tools by default.
- Admin could still manually navigate to `/admin/`, but primary UI path was incorrect.

### Fixes applied
- Admin login now redirects to `/admin/` directly.

## Lecturer

### Backend capabilities
- Access lecturer dashboard (`/dashboard/`).
- Create exams for assigned courses (`/dashboard/exams/new`, `/exams/` API).
- View exam detail and similarity pairs for owned courses (`/dashboard/exams/{id}`, `/reports/*`).
- Review pair decisions (`/dashboard/pairs/{id}/review`).

### Frontend status (before fixes)
- Dashboard links to `/dashboard/exams/new`.
- Route rendered a missing template: `dashboard/exam_new.html` was referenced but not present.
- Pair detail template extends `base.html`, but route context did not provide `user`, causing template rendering issues.
- Pair detail authorization did not verify ownership for lecturer access.

### Fixes applied
- Added missing `templates/dashboard/exam_new.html`.
- Added `user` to pair detail template context.
- Added lecturer ownership check in pair detail route.

## Student

### Backend capabilities
- View student dashboard, browse courses, enroll/unenroll.
- Submit to open exams, view own submissions and their pair summaries.

### Frontend status
- Student flows and templates are wired to matching routes.
- No blocking route-template mismatch found in current audit.

## Cross-cutting UI consistency fix
- Lecturer navigation previously had an "Exams" link to `/exams/` (JSON API endpoint).
- Updated to point to `/dashboard/exams/new` (HTML workflow).

