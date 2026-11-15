#!/usr/bin/env python3

import html
import re
import shutil
import subprocess
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

WEB_DIR = Path("/home/shaun/squirrelcam-web")
WATER_LEVEL_FILE = WEB_DIR / "water_level.json"
SOURCE_IMAGE_DIR = Path("/home/shaun/camera/squirrel_detections")
SOURCE_VIDEO_DIR = Path("/home/shaun/camera/spray_videos")

DETECTION_DIR = WEB_DIR / "detections"
ARCHIVE_DIR = WEB_DIR / "videos" / "archive"
DAYS_DIR = WEB_DIR / "days"

LATEST_IMAGE = DETECTION_DIR / "latest.jpg"
EVENT_PATTERN = re.compile(r"^(\d{8}-\d{6})_spray\.mp4$")

DETECTION_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
DAYS_DIR.mkdir(parents=True, exist_ok=True)


def run(command):
    subprocess.run(command, check=True)


def event_datetime(event_id):
    return datetime.strptime(event_id, "%Y%m%d-%H%M%S")


def display_datetime(event_id):
    return event_datetime(event_id).strftime("%B %-d, %Y • %-I:%M %p")


def display_date(day_id):
    return datetime.strptime(day_id, "%Y%m%d").strftime("%B %-d, %Y")


def convert_video(source, destination):
    if destination.exists() and destination.stat().st_mtime >= source.stat().st_mtime:
        return

    print(f"Converting {source.name} -> {destination.name}")

    run([
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        str(source),
        "-c:v",
        "libx264",
        "-preset",
        "fast",
        "-crf",
        "23",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(destination),
    ])


def copy_latest_detection():
    images = list(SOURCE_IMAGE_DIR.glob("*.jpg"))

    if not images:
        print("No detection images found.")
        return

    newest = max(images, key=lambda path: path.stat().st_mtime)
    shutil.copy2(newest, LATEST_IMAGE)

def convert_newest_event():
    """
    Convert any spray-camera videos that do not yet exist
    in the website archive. Also convert the matching
    reaction-camera video when available.
    """

    primary_videos = sorted(
        SOURCE_VIDEO_DIR.glob("*_spray.avi"),
        key=lambda path: path.stat().st_mtime
    )

    if not primary_videos:
        print("No primary spray videos found.")
        return

    converted_count = 0

    for primary_source in primary_videos:

        event_id = primary_source.name.removesuffix(
            "_spray.avi"
        )

        if event_id < "20261108-000000":
            continue

        event_id = primary_source.name.removesuffix(
            "_spray.avi"
        )

        primary_destination = (
            ARCHIVE_DIR /
            f"{event_id}_spray.mp4"
        )

        reaction_source = (
            SOURCE_VIDEO_DIR /
            f"{event_id}_reaction.avi"
        )

        reaction_destination = (
            ARCHIVE_DIR /
            f"{event_id}_reaction.mp4"
        )

        if not primary_destination.exists():

            convert_video(
                primary_source,
                primary_destination
            )

            converted_count += 1

        if (
            reaction_source.exists()
            and
            not reaction_destination.exists()
        ):

            convert_video(
                reaction_source,
                reaction_destination
            )

            converted_count += 1

    print(
        f"Video archive update complete. "
        f"Converted {converted_count} missing video files."
    )

def load_events():
    events = []

    for primary in ARCHIVE_DIR.glob("*_spray.mp4"):
        match = EVENT_PATTERN.match(primary.name)

        if not match:
            continue

        event_id = match.group(1)
        reaction = ARCHIVE_DIR / f"{event_id}_reaction.mp4"

        events.append({
            "id": event_id,
            "datetime": event_datetime(event_id),
            "primary": primary.name,
            "reaction": reaction.name if reaction.exists() else None,
            "day": event_id[:8],
        })

    return sorted(
        events,
        key=lambda event: event["datetime"],
        reverse=True
    )


def video_panel(label, source, unavailable_text=None):
    if source:
        return f"""
        <div class="camera-panel">
            <div class="camera-label">{html.escape(label)}</div>
            <video controls playsinline preload="metadata">
                <source src="{html.escape(source)}" type="video/mp4">
                Your browser does not support video playback.
            </video>
        </div>
        """

    return f"""
    <div class="camera-panel camera-unavailable">
        <div class="camera-label">{html.escape(label)}</div>
        <div class="unavailable-message">
            {html.escape(unavailable_text or "Video unavailable")}
        </div>
    </div>
    """


def event_card(event, relative_prefix=""):
    primary_source = (
        f"{relative_prefix}videos/archive/{event['primary']}"
    )

    reaction_source = None

    if event["reaction"]:
        reaction_source = (
            f"{relative_prefix}videos/archive/{event['reaction']}"
        )

    return f"""
    <article class="event-card" data-event-id="{event['id']}">
        <div class="event-heading">
            <div>
                <h3>{display_datetime(event['id'])}</h3>
                <div class="event-subtitle">Spray event</div>
            </div>

            <div class="event-actions">
                <button
                    class="stat-button like-button"
                    type="button"
                    title="Like this event"
                >
                    ❤️ <span class="like-count">0</span>
                </button>
                <span
                    class="stat-button view-stat"
                    title="Video views"
                >
                    👁 <span class="view-count">0</span>
                </span>
            </div>
        </div>

        <div class="camera-grid">
            {video_panel("Color Camera", primary_source)}
            {video_panel(
                "Global-Shutter Reaction Camera",
                reaction_source,
                "Reaction camera was not available for this event"
            )}
        </div>
    </article>
    """


def shared_styles(relative_prefix=""):
    return """
    :root {
        --forest: #244c32;
        --forest-light: #347046;
        --cream: #f5f4ee;
        --card: #ffffff;
        --text: #1f2923;
        --muted: #68746c;
        --border: #dce3dd;
        --blue: #2f80c9;
    }

    * {
        box-sizing: border-box;
    }

    body {
        margin: 0;
        color: var(--text);
        background: var(--cream);
        font-family: Arial, Helvetica, sans-serif;
    }

    header {
        color: white;
        padding: 30px 20px;
        text-align: center;
        background: linear-gradient(135deg, var(--forest), var(--forest-light));
    }

    header h1 {
        margin: 0;
        font-size: clamp(34px, 7vw, 52px);
    }

    header p {
        margin: 8px 0 0;
        opacity: 0.9;
    }

    main {
        width: min(1200px, calc(100% - 28px));
        margin: 28px auto 60px;
    }

    .dashboard-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 18px;
        margin-bottom: 28px;
    }

    .dashboard-card,
    .event-card,
    .history-card {
        background: var(--card);
        border: 1px solid var(--border);
        border-radius: 16px;
        box-shadow: 0 5px 18px rgba(31, 41, 35, 0.08);
    }

    .dashboard-card {
        padding: 22px;
    }

    .metric {
        margin-top: 10px;
        color: var(--forest);
        font-size: 42px;
        font-weight: bold;
    }

    .water-status {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        color: var(--muted);
        font-weight: bold;
    }

    .water-track {
        height: 24px;
        overflow: hidden;
        margin-top: 14px;
        border-radius: 999px;
        background: #dceaf4;
    }

    .water-fill {
        width: 0%;
        height: 100%;
        background: linear-gradient(90deg, #52a9e3, var(--blue));
    }

    .section-title {
        margin: 34px 0 16px;
    }

    .event-card {
        padding: 20px;
        margin-bottom: 22px;
    }

    .event-heading {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        gap: 18px;
        margin-bottom: 16px;
    }

    .event-heading h3 {
        margin: 0;
    }

    .event-subtitle {
        margin-top: 5px;
        color: var(--muted);
        font-size: 14px;
    }

    .event-actions {
        display: flex;
        gap: 8px;
    }

    .stat-button {
        padding: 8px 11px;
        border: 1px solid var(--border);
        border-radius: 999px;
        background: #f7f9f7;
        color: var(--muted);
    }

    .like-button {
        cursor: pointer;
    }

    .like-button:disabled {
        cursor: default;
    }

    .camera-grid {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 14px;
    }

    .camera-panel {
        overflow: hidden;
        border: 1px solid var(--border);
        border-radius: 12px;
        background: #101511;
    }

    .camera-label {
        padding: 9px 12px;
        color: white;
        background: rgba(36, 76, 50, 0.96);
        font-size: 14px;
        font-weight: bold;
    }

    video {
        display: block;
        width: 100%;
        background: black;
    }

    .camera-unavailable {
        min-height: 260px;
        background: #e9edea;
    }

    .unavailable-message {
        display: grid;
        min-height: 220px;
        place-items: center;
        padding: 24px;
        color: var(--muted);
        text-align: center;
    }

    .latest-image {
        width: 100%;
        border-radius: 12px;
    }

    .history-card {
        padding: 18px;
    }

    .history-row {
        display: flex;
        justify-content: space-between;
        gap: 16px;
        padding: 13px 4px;
        border-bottom: 1px solid var(--border);
    }

    .history-row:last-child {
        border-bottom: 0;
    }

    a {
        color: var(--forest-light);
        font-weight: bold;
        text-decoration: none;
    }

    .back-link {
        display: inline-block;
        margin-bottom: 20px;
    }

    footer {
        padding: 24px;
        color: var(--muted);
        text-align: center;
    }

    @media (max-width: 760px) {
        .dashboard-grid,
        .camera-grid {
            grid-template-columns: 1fr;
        }

        .event-heading {
            flex-direction: column;
        }

        .camera-unavailable {
            min-height: 210px;
        }

        .unavailable-message {
            min-height: 170px;
        }
    }
    """

def page_shell(title, body, relative_prefix=""):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)}</title>
    <style>{shared_styles(relative_prefix)}</style>
</head>

<body>

<header>
    <h1>🐿️ SquirrelCam</h1>
    <p>Dual-camera squirrel detection and deterrent system</p>
</header>

{body}

<footer>
    SquirrelCam • Raspberry Pi wildlife monitoring
</footer>

<script src="{relative_prefix}live_stats.js"></script>

</body>
</html>
"""

def build_day_pages(events_by_day):
    current_pages = set()

    for day_id, events in events_by_day.items():
        filename = f"{day_id}.html"
        current_pages.add(filename)

        cards = "\n".join(
            event_card(event, relative_prefix="../")
            for event in events
        )

        body = f"""
        <main>
            <a class="back-link" href="../index.html">← Back to dashboard</a>
            <h2>{display_date(day_id)}</h2>
            <p><strong>{len(events)} spray events</strong></p>
            {cards}
        </main>
        """

        (DAYS_DIR / filename).write_text(
            page_shell(
                f"SquirrelCam • {display_date(day_id)}",
                body,
                relative_prefix="../"
            ),
            encoding="utf-8"
        )

    for existing in DAYS_DIR.glob("*.html"):
        if existing.name not in current_pages:
            existing.unlink()


def build_homepage(events, events_by_day):
    latest_events = events[:10]
    today_id = datetime.now().strftime("%Y%m%d")
    today_count = len(events_by_day.get(today_id, []))

    # Load the most recent water-level reading
    water_percentage = None
    water_status = "UNKNOWN"
    water_distance = None

    if WATER_LEVEL_FILE.exists():
        try:
            water_data = json.loads(
                WATER_LEVEL_FILE.read_text(
                    encoding="utf-8"
                )
            )

            water_percentage = int(
                water_data["percentage"]
            )

            water_status = water_data.get(
                "status",
                "UNKNOWN"
            )

            water_distance = water_data.get(
                "distance_mm"
            )

        except Exception as error:
            print(
                f"Water level warning: {error}"
            )

    if water_percentage is None:
        water_label = "Sensor unavailable"
        water_width = 0
        water_color = "#9aa39d"

    else:
        water_label = f"{water_percentage}%"
        water_width = water_percentage

        if water_percentage < 20:
            water_color = "#d64545"
        elif water_percentage < 50:
            water_color = "#e0a325"
        else:
            water_color = "#3f9b58"

    latest_cards = "\n".join(
        event_card(event)
        for event in latest_events
    )

    history_rows = []

    for day_id in sorted(events_by_day.keys(), reverse=True):
        count = len(events_by_day[day_id])

        history_rows.append(f"""
        <div class="history-row">
            <a href="days/{day_id}.html">{display_date(day_id)}</a>
            <strong>{count} sprays</strong>
        </div>
        """)

    latest_detection_section = ""

    if LATEST_IMAGE.exists():
        latest_detection_section = """
        <h2 class="section-title">Latest Detection</h2>
        <div class="dashboard-card">
            <img class="latest-image"
                 src="detections/latest.jpg"
                 alt="Latest SquirrelCam detection">
        </div>
        """

    body = f"""
    <main>
        <div class="dashboard-grid">
            <section class="dashboard-card">
                <h2>💦 Today's Activity</h2>
                <div class="metric">{today_count}</div>
                <div>sprays today</div>
            </section>

            <section class="dashboard-card">
                <h2>💧 Water Tank</h2>
                <div class="water-status">
                    <span>5-gallon supply</span>
                    <span>{water_label}</span>
                </div>
                <div class="water-track">
                    <div class="water-fill"
                         style="width:{water_width}%; background:{water_color};">
                    </div>
                </div>
            </section>
        </div>

        {latest_detection_section}

        <h2 class="section-title">Latest Reactions</h2>
        {latest_cards or '<p>No spray events are available yet.</p>'}

        <h2 class="section-title">Browse by Day</h2>
        <section class="history-card">
            {''.join(history_rows) or '<p>No history is available yet.</p>'}
        </section>
    </main>
    """

    (WEB_DIR / "index.html").write_text(
        page_shell("SquirrelCam Dashboard", body),
        encoding="utf-8"
    )


def main():
    copy_latest_detection()
    convert_newest_event()

    events = load_events()
    events_by_day = defaultdict(list)

    for event in events:
        events_by_day[event["day"]].append(event)

    build_day_pages(events_by_day)
    build_homepage(events, events_by_day)

    print()
    print(f"Dashboard generated with {len(events)} spray events.")
    print(f"Daily pages generated: {len(events_by_day)}")
    print("No Git commit or push was performed.")


if __name__ == "__main__":
    main()
