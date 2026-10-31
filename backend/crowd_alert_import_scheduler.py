import re
import subprocess
import sys
import time
from pathlib import Path
from threading import Event, Thread

SCRIPTS_FOLDER = (
    Path(__file__).resolve().parents[1]
    / "database"
    / "scripts"
)

UPDATE_INTERVAL = 15 * 60


def crowd_summary(output):
    matches = re.findall(
        r"^\w+: (\d+) new, (\d+) changed, (\d+) unchanged$",
        output,
        flags=re.MULTILINE,
    )

    if not matches:
        return "Crowd: no observations reported"

    new = sum(int(match[0]) for match in matches)
    changed = sum(int(match[1]) for match in matches)
    unchanged = sum(int(match[2]) for match in matches)

    return (
        f"Crowd: {new} new, "
        f"{changed} changed, "
        f"{unchanged} unchanged"
    )


def alerts_summary(output):
    if "new service-status snapshot saved" in output:
        return "Alerts: new snapshot stored"

    if "response unchanged" in output:
        return "Alerts: unchanged"

    return "Alerts: no result reported"


def collect_data(stop_event):
    jobs = (
        ("density_import.py", "Crowd", crowd_summary),
        ("alerts_import.py", "Alerts", alerts_summary),
    )

    while not stop_event.is_set():
        started = time.monotonic()
        summaries = []

        for filename, label, summarise in jobs:
            if stop_event.is_set():
                break

            try:
                result = subprocess.run(
                    [sys.executable, str(SCRIPTS_FOLDER / filename)],
                    timeout=360,
                    capture_output=True,
                    text=True,
                    errors="replace",
                )

                summary = summarise(result.stdout)

                if result.returncode != 0:
                    summary += " [FAILED / incomplete]"

                    errors = [
                        line
                        for line in result.stdout.splitlines()
                        if "failed" in line.lower()
                    ]

                    if result.stderr.strip():
                        errors.append(result.stderr.strip())

                    if errors:
                        print(
                            f"[{label}] " + "\n".join(errors),
                            flush=True,
                        )

                summaries.append(summary)

            except (subprocess.TimeoutExpired, OSError) as error:
                summaries.append(
                    f"{label}: FAILED ({type(error).__name__})"
                )

        if summaries:
            print(
                f"[{time.strftime('%H:%M:%S')}] "
                + " | ".join(summaries),
                flush=True,
            )

        remaining = max(
            0,
            UPDATE_INTERVAL - (time.monotonic() - started),
        )
        stop_event.wait(remaining)


def start_collector():
    stop_event = Event()

    worker = Thread(
        target=collect_data,
        args=(stop_event,),
        name="crowd-alert-collector",
        daemon=True,
    )
    worker.start()

    return stop_event