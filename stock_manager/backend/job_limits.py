"""Stock-manager instances of JobRunGuard (HTTP cooldown; cron is not limited)."""

from constant import (
    CLEANUP_ARCHIVE_HTTP_COOLDOWN_SECONDS,
    DAILY_UPDATE_HTTP_COOLDOWN_SECONDS,
)
from llm_guard import JobRunGuard

daily_update_guard = JobRunGuard(
    DAILY_UPDATE_HTTP_COOLDOWN_SECONDS,
    busy_detail="Daily update already running",
    cooldown_detail=(
        "Daily update was triggered too recently; try again later. "
        "The scheduled job is not affected."
    ),
    skip_log="Skipping scheduled daily-update; a run is already in progress",
)
cleanup_archive_guard = JobRunGuard(
    CLEANUP_ARCHIVE_HTTP_COOLDOWN_SECONDS,
    busy_detail="Cleanup/archive already running",
    cooldown_detail=(
        "Cleanup/archive was triggered too recently; try again later. "
        "The scheduled job is not affected."
    ),
    skip_log="Skipping scheduled cleanup-archive; a run is already in progress",
)
