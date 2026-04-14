"""
Scheduled jobs module.
"""

from app.jobs.scheduler import init_scheduler, shutdown_scheduler
from app.jobs.reminders import send_appointment_reminders
from app.jobs.reports import send_weekly_report
from app.jobs.backup import backup_database
from app.jobs.sync_calendar import sync_calendar_events
from app.jobs.auto_resume import auto_resume_paused_conversations

__all__ = [
    "init_scheduler",
    "shutdown_scheduler",
    "send_appointment_reminders",
    "send_weekly_report",
    "backup_database",
    "sync_calendar_events",
    "auto_resume_paused_conversations",
]
