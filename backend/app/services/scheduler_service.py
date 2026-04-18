from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler

from app.database import db
from app.services.performance_service import refresh_user_performance


def _maintenance_job() -> None:
    users = db.fetch_all("SELECT id FROM users")
    for user in users:
        refresh_user_performance(user["id"])


class SchedulerService:
    def __init__(self) -> None:
        self.scheduler = BackgroundScheduler(timezone="UTC")
        self.started = False

    def start(self, interval_minutes: int) -> None:
        if self.started:
            return
        self.scheduler.add_job(_maintenance_job, "interval", minutes=interval_minutes, id="maintenance", replace_existing=True)
        self.scheduler.start()
        self.started = True

    def stop(self) -> None:
        if self.started:
            self.scheduler.shutdown(wait=False)
            self.started = False


scheduler_service = SchedulerService()
