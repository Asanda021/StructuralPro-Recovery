# P61 — Production Observability

قرارداد Evidence برای پایش عملیاتی اضافه شد: سرویس، محیط، رخداد، وضعیت، منبع و زمان مشاهده.

وضعیت healthy به go، وضعیت degraded/unknown به needs_evidence و failed به no_go منجر می‌شود.

این فاز هیچ uptime، سلامت سرویس، SLA یا KPI واقعی را جعل نمی‌کند؛ این نتایج فقط با شواهد واقعی پایش تولید معتبر هستند.
