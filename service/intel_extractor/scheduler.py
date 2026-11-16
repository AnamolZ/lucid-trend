import time
from datetime import datetime
from service.intel_extractor.pipeline import run_pipeline

INTERVAL_MINUTES = 20
INTERVAL_SECONDS = INTERVAL_MINUTES * 60


def start_scheduler():
    """Runs social intel extraction, synthesis, and edge publication every 20 minutes."""
    print("=" * 65)
    print(f"Starting Lucid Trend 20-Minute Intelligence Scheduler (Interval: {INTERVAL_MINUTES}m)")
    print("=" * 65)

    cycle_count = 1
    while True:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"\n[Scheduler] Running Cycle #{cycle_count} at {now_str}...")

        try:
            run_pipeline()
        except KeyboardInterrupt:
            print("\n[Scheduler] Stopped by user.")
            break
        except Exception as e:
            print(f"[Scheduler] Error encountered during cycle: {e}")

        print(f"\n[Scheduler] Cycle #{cycle_count} finished. Next run in {INTERVAL_MINUTES} minutes.")
        cycle_count += 1

        try:
            time.sleep(INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\n[Scheduler] Stopped by user.")
            break


if __name__ == "__main__":
    start_scheduler()
