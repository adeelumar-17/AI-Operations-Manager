import sys
import time

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from backend.app.scheduler.scheduler import scheduler, start_scheduler, stop_scheduler
from backend.app.scheduler.jobs import process_due_followups


def test_scheduler_lifecycle() -> bool:
    print("=" * 60)
    print("M7 Scheduling Test: Lifecycle & Job Execution")
    print("=" * 60)

    # 1. Test starting the scheduler
    start_scheduler(interval_seconds=5)
    assert scheduler.running, "Expected scheduler to be running"
    print("✓ Scheduler started successfully.")

    # 2. Check registered jobs
    job = scheduler.get_job("process_due_followups")
    assert job is not None, "Expected 'process_due_followups' job to be registered"
    print(f"✓ Job registered: {job.name} (trigger: {job.trigger})")

    # 3. Test running the job directly
    count = process_due_followups()
    print(f"✓ Executed process_due_followups directly: processed {count} tasks.")

    # 4. Test stopping the scheduler
    stop_scheduler()
    assert not scheduler.running, "Expected scheduler to be stopped"
    print("✓ Scheduler stopped cleanly.")

    print("\n" + "=" * 60)
    print("ALL M7 SCHEDULER TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    test_scheduler_lifecycle()
