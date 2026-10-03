"""Manages dynamic scheduling and live 12-hour schedule reshuffling."""

import random
import logging
import asyncio
import schedule

_SCHEDULE_STATE = {
    "times": ["05:00", "17:00"],
    "callback": None
}

def register_pipeline_callback(callback):
    """Registers the async daily pipeline runner callback."""
    _SCHEDULE_STATE["callback"] = callback

def get_active_schedule() -> list:
    """Returns the list of currently scheduled daily execution times."""
    return list(_SCHEDULE_STATE["times"])

def apply_schedule(times: list = None) -> list:
    """Registers the pipeline schedule into the schedule library."""
    target_times = times or _SCHEDULE_STATE["times"]
    callback = _SCHEDULE_STATE["callback"]

    schedule.clear("daily_pipeline")

    for t in target_times:
        if callback:
            schedule.every().day.at(t).do(lambda cb=callback: asyncio.run(cb())).tag("daily_pipeline")
        else:
            schedule.every().day.at(t).do(lambda: None).tag("daily_pipeline")

    _SCHEDULE_STATE["times"] = list(target_times)
    logging.info(
        f"[Scheduler] Active daily pipeline schedule: {', '.join(target_times)} Asia/Kathmandu (12h gap)."
    )
    return list(target_times)

def reshuffle_schedule() -> tuple:
    """Generates two new random daily execution times maintaining an exact 12-hour interval."""
    # Pick a random initial time in the first half of the day (00:00 to 11:59)
    h1 = random.randint(0, 11)
    m = random.randint(0, 59)

    # Calculate second execution time exactly 12 hours later
    h2 = (h1 + 12) % 24

    time1 = f"{h1:02d}:{m:02d}"
    time2 = f"{h2:02d}:{m:02d}"
    new_times = [time1, time2]

    apply_schedule(new_times)

    logging.info(
        f"[Scheduler Reshuffle] Schedule updated to {time1} and {time2} Asia/Kathmandu (12h gap)."
    )
    return time1, time2
