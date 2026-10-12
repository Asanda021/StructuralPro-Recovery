# Priority 18 — Project Management Depth

## Scope
عمق عملیاتی مدیریت پروژه، بدون ورود به طراحی سازه یا بهینه‌سازی خودکار برنامه.

## Added
- weighted schedule progress
- overdue task detection
- task status validation
- predecessor/dependency validation
- dependency-ready / blocked task detection
- planned vs actual end-date variance
- delay days
- daily report aggregation
- workforce summary
- resource summary by kind
- received-material summary
- meeting follow-up tracking
- unified management dashboard
- persistence through the application service
- backward-compatible dedicated project-management fields

## Persistence
Management data uses dedicated project fields: project_schedule_tasks, project_daily_reports, project_resources, project_materials, project_meetings.
Legacy project fields are not rewritten.
