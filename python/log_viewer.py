"""Lightweight Flask app to browse and analyse batch (scanning) logs."""

from __future__ import annotations

import copy
import csv
import json
import os
import shutil
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock

from flask import Flask, abort, render_template_string, request, send_from_directory

from config import HEADER_TEXT, FOOTER_TEXT, LOG_FOLDER


APP_ROOT = Path(__file__).resolve().parent
BATCH_LOG_DIR = APP_ROOT / LOG_FOLDER
STATIC_DIR = APP_ROOT / "static"
HEADER_LOGO_FILENAME = os.environ.get("LOG_VIEWER_LOGO", "molbio-black-logo.png")
FAVICON_FILENAME = os.environ.get("LOG_VIEWER_FAVICON", "footer-logo.png")


app = Flask(__name__)

_CACHE_LOCK = Lock()
_CACHE = {
    "batch_stats": {},  # filename -> {"signature": sig, "data": {...}}
    "daily_trends": {"signature": None, "data": None},
}


def _logo_context() -> dict:
    header_path = STATIC_DIR / HEADER_LOGO_FILENAME
    favicon_path = STATIC_DIR / FAVICON_FILENAME
    return {
        "header_logo_available": header_path.exists(),
        "header_logo_filename": HEADER_LOGO_FILENAME,
        "favicon_available": favicon_path.exists(),
        "favicon_filename": FAVICON_FILENAME,
    }


def _human_size(num_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if num_bytes < 1024 or unit == "GB":
            return f"{num_bytes:.1f} {unit}"
        num_bytes /= 1024
    return f"{num_bytes:.1f} GB"


def _list_csv(directory: Path) -> list[dict]:
    if not directory.exists():
        return []
    entries = []
    for path in directory.glob("*.csv"):
        try:
            stats = path.stat()
        except OSError:
            continue
        entries.append(
            {
                "name": path.name,
                "mtime": stats.st_mtime,
                "mtime_display": datetime.fromtimestamp(stats.st_mtime).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
                "size": stats.st_size,
                "size_display": _human_size(float(stats.st_size)),
            }
        )
    return sorted(entries, key=lambda item: item["mtime"], reverse=True)


def _count_scans(files: list[dict]) -> tuple[int, int]:
    total = 0
    total_pass = 0
    for entry in files:
        path = BATCH_LOG_DIR / entry["name"]
        try:
            with path.open(newline="", encoding="utf-8") as handle:
                reader = csv.reader(handle)
                header = next(reader, None)
                for row in reader:
                    if not row:
                        continue
                    total += 1
                    status = row[4].strip().upper() if len(row) > 4 else ""
                    if status == "PASS":
                        total_pass += 1
        except (OSError, csv.Error):
            continue
    return total, total_pass


def _file_signature(path: Path) -> tuple | None:
    try:
        stats = path.stat()
        return (stats.st_mtime, stats.st_size)
    except OSError:
        return None


def _read_log_rows(path: Path) -> list[dict]:
    rows: list[dict] = []
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
            expected = ["Timestamp", "BatchNumber", "Mould", "QRCode", "Status"]
            header_is_present = header and [h.strip() for h in header] == expected
            if not header_is_present and header:
                # treat header as first row
                rows.append({
                    "timestamp": header[0].strip() if header else "",
                    "batch": header[1].strip() if len(header) > 1 else "",
                    "mould": header[2].strip() if len(header) > 2 else "",
                    "qr": header[3].strip() if len(header) > 3 else "",
                    "status": header[4].strip() if len(header) > 4 else "",
                })
            for row in reader:
                if not row:
                    continue
                rows.append(
                    {
                        "timestamp": row[0].strip() if len(row) > 0 else "",
                        "batch": row[1].strip() if len(row) > 1 else "",
                        "mould": row[2].strip() if len(row) > 2 else "",
                        "qr": row[3].strip() if len(row) > 3 else "",
                        "status": row[4].strip().upper() if len(row) > 4 else "",
                    }
                )
    except (OSError, csv.Error):
        return []
    return rows


def _batch_stats(filename: str) -> dict:
    path = (BATCH_LOG_DIR / filename).resolve()
    if not path.exists() or path.parent != BATCH_LOG_DIR.resolve():
        abort(404)

    signature = _file_signature(path)
    with _CACHE_LOCK:
        cached = _CACHE["batch_stats"].get(filename)
        if cached and cached["signature"] == signature:
            return copy.deepcopy(cached["data"])

    rows = _read_log_rows(path)
    if not rows:
        result = {
            "filename": filename,
            "total": 0,
            "pass": 0,
            "duplicate": 0,
            "other": 0,
            "first_time": None,
            "last_time": None,
            "timeline": [],
            "chart_labels": [],
            "chart_pass": [],
            "chart_duplicate": [],
            "chart_other": [],
        }
        with _CACHE_LOCK:
            _CACHE["batch_stats"][filename] = {
                "signature": signature,
                "data": copy.deepcopy(result),
            }
        return result

    total = len(rows)
    pass_count = sum(1 for r in rows if r["status"] == "PASS")
    duplicate_count = sum(1 for r in rows if r["status"] == "DUPLICATE")
    other_count = total - pass_count - duplicate_count

    def _parse_ts(ts: str) -> datetime | None:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
            try:
                return datetime.strptime(ts, fmt)
            except ValueError:
                continue
        return None

    timestamps = [t for r in rows if (t := _parse_ts(r["timestamp"]))]
    first_time = min(timestamps).strftime("%Y-%m-%d %H:%M:%S") if timestamps else None
    last_time = max(timestamps).strftime("%Y-%m-%d %H:%M:%S") if timestamps else None

    timeline = defaultdict(lambda: {"PASS": 0, "DUPLICATE": 0, "OTHER": 0})
    for r in rows:
        ts = _parse_ts(r["timestamp"])
        if not ts:
            continue
        bucket = ts.replace(minute=0, second=0, microsecond=0)
        status = r["status"] if r["status"] in ("PASS", "DUPLICATE") else "OTHER"
        timeline[bucket][status] += 1

    chart_labels = []
    chart_pass = []
    chart_duplicate = []
    chart_other = []
    for bucket in sorted(timeline.keys()):
        chart_labels.append(bucket.strftime("%Y-%m-%d %H:%M"))
        chart_pass.append(timeline[bucket]["PASS"])
        chart_duplicate.append(timeline[bucket]["DUPLICATE"])
        chart_other.append(timeline[bucket]["OTHER"])

    return {
        "filename": filename,
        "total": total,
        "pass": pass_count,
        "duplicate": duplicate_count,
        "other": other_count,
        "first_time": first_time,
        "last_time": last_time,
        "chart_labels": chart_labels,
        "chart_pass": chart_pass,
        "chart_duplicate": chart_duplicate,
        "chart_other": chart_other,
    }

    with _CACHE_LOCK:
        _CACHE["batch_stats"][filename] = {
            "signature": signature,
            "data": copy.deepcopy(result),
        }
    return result


def _health_metrics() -> dict:
    temp = None
    for path in ("/sys/class/thermal/thermal_zone0/temp",):
        try:
            with open(path, "r", encoding="utf-8") as handle:
                temp = float(handle.read().strip()) / 1000.0
                break
        except (OSError, ValueError):
            continue

    disk = shutil.disk_usage(BATCH_LOG_DIR)
    disk_used_pct = (disk.used / disk.total) * 100 if disk.total else 0

    try:
        with open("/proc/uptime", "r", encoding="utf-8") as handle:
            uptime_seconds = float(handle.read().split()[0])
    except (OSError, ValueError):
        uptime_seconds = 0
    uptime = timedelta(seconds=int(uptime_seconds))

    latest_mtime = None
    for path in BATCH_LOG_DIR.glob("*.csv"):
        try:
            mtime = path.stat().st_mtime
            if not latest_mtime or mtime > latest_mtime:
                latest_mtime = mtime
        except OSError:
            continue
    last_event = (
        datetime.fromtimestamp(latest_mtime).strftime("%Y-%m-%d %H:%M:%S")
        if latest_mtime
        else "N/A"
    )
    age_seconds = time.time() - latest_mtime if latest_mtime else None

    return {
        "temp": f"{temp:.1f} °C" if temp is not None else "N/A",
        "disk": f"{disk_used_pct:.1f}% used",
        "uptime": str(uptime),
        "last_event": last_event,
        "last_event_age": f"{int(age_seconds // 60)} mins ago" if age_seconds else "N/A",
    }


def _daily_trends(files: list[dict]) -> dict:
    signature = tuple((entry["name"], entry.get("mtime"), entry.get("size")) for entry in files)
    with _CACHE_LOCK:
        cached = _CACHE["daily_trends"]
        if cached["signature"] == signature and cached["data"] is not None:
            return copy.deepcopy(cached["data"])

    totals = defaultdict(lambda: {"total": 0, "pass": 0, "duplicate": 0})
    for entry in files:
        path = BATCH_LOG_DIR / entry["name"]
        rows = _read_log_rows(path)
        for row in rows:
            ts = row["timestamp"]
            for fmt in ("%Y-%m-%d %H:%M:%S", "%d/%m/%Y %H:%M:%S"):
                try:
                    day = datetime.strptime(ts, fmt).date()
                    break
                except ValueError:
                    day = None
            if not day:
                continue
            totals[day]["total"] += 1
            status = row["status"]
            if status == "PASS":
                totals[day]["pass"] += 1
            elif status == "DUPLICATE":
                totals[day]["duplicate"] += 1

    ordered_days = sorted(totals.keys())
    result = {
        "labels": [day.strftime("%Y-%m-%d") for day in ordered_days],
        "total": [totals[day]["total"] for day in ordered_days],
        "pass": [totals[day]["pass"] for day in ordered_days],
        "duplicate": [totals[day]["duplicate"] for day in ordered_days],
    }
    with _CACHE_LOCK:
        _CACHE["daily_trends"] = {
            "signature": signature,
            "data": copy.deepcopy(result),
        }
    return result


TEMPLATE = """
<!doctype html>
<html lang="en">
    <head>
        <meta charset="utf-8" />
        <title>Dashboard</title>
        {% if favicon_available %}
        <link rel="icon" type="image/png" href="{{ url_for('static', filename=favicon_filename) }}" />
        {% endif %}
        <style>
            * { box-sizing: border-box; }
            body { font-family: "Segoe UI", Arial, sans-serif; background: #f8fafc; color: #1f2937; margin:0; padding-top:150px; padding-bottom:80px; }
            header, footer { position:fixed; left:0; z-index:200; width:100%; background:#ffffff; box-shadow:0 6px 18px -16px rgba(15,23,42,0.6); }
            header { top:0; border-bottom:1px solid #e2e8f0; }
            footer { bottom:0; border-top:1px solid #e2e8f0; text-align:center; color:#475569; padding:1rem 0; }
            .header-inner { width: min(1100px, 94%); margin: 0 auto; display:flex; align-items:center; gap:1.2rem; padding:1.1rem 0.5rem; }
            .header-inner img { max-height:68px; border-radius:8px; }
            h1 { color:#ff3b30; margin:0; font-size:2rem; }
            h2 { color: #0f172a; margin-top: 0; }
            a { color: #2563eb; text-decoration: none; }
            a:hover { text-decoration: underline; }
            .container { width: min(1100px, 94%); margin: 0 auto; }
            table { width: 100%; border-collapse: collapse; margin-bottom: 1.5rem; background:#ffffff; border-radius:8px; overflow:hidden; box-shadow: 0 10px 25px -20px rgba(15,23,42,0.6); }
            th, td { padding: 0.65rem 0.75rem; border-bottom: 1px solid #e2e8f0; text-align: left; }
            thead th { background:#f1f5f9; font-weight:600; color:#0f172a; }
            tr:hover { background: #f8fafc; }
            .empty { font-style: italic; color: #64748b; padding: 1rem 0; }
            main { flex:1 0 auto; }
            nav { margin:1.2rem 0 1rem; display:flex; gap:1rem; }
            nav a { color:#0f172a; font-weight:600; padding:0.4rem 0.75rem; border-radius:6px; background:#e2e8f0; }
            nav a:hover { color:#ffffff; background:#1d4ed8; }
            .page-title { font-family: Arial, sans-serif; font-weight:700; color:#0f172a; margin:0 0 1.2rem 0; font-size:1.35rem; }
            .search-group { margin-bottom: 1rem; display:flex; gap:0.65rem; align-items:center; }
            input[type="search"] { padding:0.45rem 0.65rem; border:1px solid #cbd5f5; border-radius:4px; min-width:260px; background:#ffffff; }
            .refresh-toggle { margin: 0 0 1rem 0; color:#64748b; font-size:0.9rem; display:flex; flex-wrap:wrap; align-items:center; gap:0.75rem; }
            .last-refresh { font-weight:500; color:#475569; }
            .summary-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:1rem; margin-bottom:1.5rem; }
            .summary-card { background:#ffffff; border-radius:10px; padding:1rem 1.1rem; box-shadow: 0 12px 28px -18px rgba(15,23,42,0.45); }
            .summary-title { font-size:0.9rem; text-transform:uppercase; letter-spacing:0.08em; color:#64748b; margin-bottom:0.4rem; }
            .summary-value { font-size:1.4rem; font-weight:600; color:#0f172a; }
            .summary-subtext { font-size:0.85rem; color:#6b7280; }
            .health-panel { background:#ffffff; border-radius:10px; padding:1rem 1.2rem; box-shadow: 0 12px 28px -18px rgba(15,23,42,0.45); margin-bottom:1.5rem; }
            .health-grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap:1rem; }
            .health-item { font-size:0.95rem; }
            .health-label { font-weight:600; color:#0f172a; display:block; text-transform:uppercase; letter-spacing:0.06em; margin-bottom:0.3rem; font-size:0.78rem; }
            .actions a { display:inline-block; padding:0.35rem 0.65rem; border-radius:4px; background:#2563eb; color:#ffffff; font-size:0.85rem; margin-right:0.4rem; }
            .actions a:last-child { margin-right:0; background:#0f172a; }
            .actions a:hover { filter:brightness(1.05); }
            @media (max-width:768px) {
                .header-inner { flex-direction:column; align-items:flex-start; }
                nav { font-size:0.95rem; }
                table, thead, tbody, th, td, tr { display:block; }
                thead { display:none; }
                tr { margin-bottom:1rem; box-shadow: 0 10px 20px -18px rgba(15,23,42,0.6); border-radius:8px; overflow:hidden; }
                td { border:none; border-bottom:1px solid #e2e8f0; padding:0.65rem 1rem; }
                td::before { content:attr(data-label); font-weight:600; display:block; color:#0f172a; margin-bottom:0.25rem; text-transform:uppercase; font-size:0.75rem; letter-spacing:0.08em; }
            }
        </style>
        <script>
            const DASHBOARD_REFRESH_INTERVAL = 30000;
            const DASHBOARD_REFRESH_STORAGE_KEY = "batch_dashboard_autorefresh";

            function initAutoRefresh(intervalMs, storageKey, checkboxId) {
                const toggle = document.getElementById(checkboxId);
                if (toggle) {
                    const stored = localStorage.getItem(storageKey);
                    if (stored === "0") {
                        toggle.checked = false;
                    }
                    toggle.addEventListener("change", () => {
                        localStorage.setItem(storageKey, toggle.checked ? "1" : "0");
                    });
                }

                setInterval(() => {
                    const toggleElement = document.getElementById(checkboxId);
                    const enabled = !toggleElement || toggleElement.checked;
                    if (!enabled) {
                        return;
                    }
                    if (!document.hidden) {
                        window.location.reload();
                    }
                }, intervalMs);
            }

            function formatDateTime(date) {
                const day = String(date.getDate()).padStart(2, "0");
                const month = String(date.getMonth() + 1).padStart(2, "0");
                const year = date.getFullYear();
                const hours = String(date.getHours()).padStart(2, "0");
                const minutes = String(date.getMinutes()).padStart(2, "0");
                const seconds = String(date.getSeconds()).padStart(2, "0");
                return `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`;
            }

            function updateLastRefreshed(labelId) {
                const label = document.getElementById(labelId);
                if (!label) {
                    return;
                }
                label.textContent = formatDateTime(new Date());
            }

            function filterTable(inputId, tableId) {
                const query = document.getElementById(inputId).value.toLowerCase();
                const rows = document.querySelectorAll(`#${tableId} tbody tr`);
                rows.forEach(row => {
                    const text = row.getAttribute('data-filename');
                    row.style.display = text.includes(query) ? '' : 'none';
                });
            }
            document.addEventListener("DOMContentLoaded", () => {
                updateLastRefreshed("last-refresh-label");
                initAutoRefresh(DASHBOARD_REFRESH_INTERVAL, DASHBOARD_REFRESH_STORAGE_KEY, "auto-refresh-toggle");
            });
        </script>
    </head>
    <body>
        <header>
            <div class="header-inner">
            {% if header_logo_available %}
                <img src="{{ url_for('static', filename=header_logo_filename) }}" alt="Company Logo" />
            {% endif %}
            <h1>{{ company_name }}</h1>
            </div>
        </header>
        <div class="container">
        <h2 class="page-title">Automatic Cartridge Scanning JIG Data</h2>
        <nav>
            <a href="#batch">Batch Logs</a>
            <a href="/trends">Trends</a>
        </nav>
        <div class="refresh-toggle">
            <label>
                <input type="checkbox" id="auto-refresh-toggle" checked />
                Auto refresh dashboard every 30s
            </label>
            <span class="last-refresh">Last refresh: <span id="last-refresh-label">--</span></span>
        </div>
        <section class="summary-grid">
            <div class="summary-card">
                <div class="summary-title">Batch logs</div>
                <div class="summary-value">{{ batch_count }}</div>
                <div class="summary-subtext">{{ batch_total_size }} total</div>
            </div>
            <div class="summary-card">
                <div class="summary-title">Total scans</div>
                <div class="summary-value">{{ total_scans }}</div>
                <div class="summary-subtext">PASS: {{ total_pass }}</div>
            </div>
        </section>
        <section class="health-panel">
            <h2>System Health</h2>
            <div class="health-grid">
                <div class="health-item"><span class="health-label">CPU Temp</span>{{ health.temp }}</div>
                <div class="health-item"><span class="health-label">Disk Usage</span>{{ health.disk }}</div>
                <div class="health-item"><span class="health-label">Uptime</span>{{ health.uptime }}</div>
                <div class="health-item"><span class="health-label">Last Scan</span>{{ health.last_event }}<br><small>{{ health.last_event_age }}</small></div>
            </div>
        </section>
        <main>
        <section id="batch">
            <h2>Batch Logs</h2>
            <div class="search-group">
                <label for="batch-search">Search:</label>
                <input type="search" id="batch-search" placeholder="Filter batch logs..." oninput="filterTable('batch-search', 'batch-table')" />
            </div>
            {% if batch_files %}
            <table id="batch-table">
                <thead><tr><th>Filename</th><th>Modified</th><th>Size</th><th>Actions</th></tr></thead>
                <tbody>
                {% for file in batch_files %}
                    <tr data-filename="{{ file.name | lower }}">
                        <td data-label="Filename">{{ file.name }}</td>
                        <td data-label="Modified">{{ file.mtime_display }}</td>
                        <td data-label="Size">{{ file.size_display }}</td>
                        <td data-label="Actions" class="actions">
                            <a href="/batch/{{ file.name }}" target="_blank">View</a>
                            <a href="/batch/{{ file.name }}?download=1">Download</a>
                            <a href="/batch/{{ file.name }}/details">Details</a>
                        </td>
                    </tr>
                {% endfor %}
                </tbody>
            </table>
            {% else %}
                <p class="empty">No batch logs available.</p>
            {% endif %}
        </section>

        </main>
        </div>
        <footer>{{ footer_text }}</footer>
    </body>
</html>
"""


DETAIL_TEMPLATE = """
<!doctype html>
<html lang="en">
    <head>
        <meta charset="utf-8" />
        <title>Batch Details - {{ stats.filename }}</title>
        {% if favicon_available %}
        <link rel="icon" type="image/png" href="{{ url_for('static', filename=favicon_filename) }}" />
        {% endif %}
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body { font-family: "Segoe UI", Arial, sans-serif; background:#f8fafc; color:#1f2937; margin:0; padding:2rem; }
            a { color:#2563eb; text-decoration:none; }
            a:hover { text-decoration:underline; }
            .container { max-width:960px; margin:0 auto; background:#ffffff; border-radius:12px; box-shadow:0 16px 40px -30px rgba(15,23,42,0.7); padding:2rem; }
            h1 { color:#ff3b30; margin-top:0; }
            .grid { display:grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap:1rem; margin-bottom:2rem; }
            .card { background:#f1f5f9; border-radius:8px; padding:1rem; }
            .label { text-transform:uppercase; letter-spacing:0.08em; font-size:0.75rem; color:#64748b; margin-bottom:0.35rem; display:block; }
            canvas { background:#ffffff; border-radius:8px; box-shadow:0 12px 28px -18px rgba(15,23,42,0.45); padding:1rem; }
            .toolbar { display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:0.75rem; margin-bottom:1rem; }
            .refresh-toggle { color:#64748b; font-size:0.9rem; display:flex; flex-wrap:wrap; align-items:center; gap:0.75rem; }
            .last-refresh { font-weight:500; color:#475569; }
        </style>
        <script>
            const DETAIL_REFRESH_INTERVAL = 60000;
            const DETAIL_REFRESH_STORAGE_KEY = "batch_dashboard_autorefresh";

            function formatDateTime(date) {
                const day = String(date.getDate()).padStart(2, "0");
                const month = String(date.getMonth() + 1).padStart(2, "0");
                const year = date.getFullYear();
                const hours = String(date.getHours()).padStart(2, "0");
                const minutes = String(date.getMinutes()).padStart(2, "0");
                const seconds = String(date.getSeconds()).padStart(2, "0");
                return `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`;
            }

            function updateLastRefreshed(labelId) {
                const label = document.getElementById(labelId);
                if (!label) {
                    return;
                }
                label.textContent = formatDateTime(new Date());
            }

            function initDetailAutoRefresh() {
                const toggle = document.getElementById("auto-refresh-toggle");
                if (toggle) {
                    const stored = localStorage.getItem(DETAIL_REFRESH_STORAGE_KEY);
                    if (stored === "0") {
                        toggle.checked = false;
                    }
                    toggle.addEventListener("change", () => {
                        localStorage.setItem(DETAIL_REFRESH_STORAGE_KEY, toggle.checked ? "1" : "0");
                    });
                }
                updateLastRefreshed("last-refresh-label");
                setInterval(() => {
                    const enabled = !toggle || toggle.checked;
                    if (!enabled) {
                        return;
                    }
                    if (!document.hidden) {
                        window.location.reload();
                    }
                }, DETAIL_REFRESH_INTERVAL);
            }
            document.addEventListener("DOMContentLoaded", initDetailAutoRefresh);
        </script>
    </head>
    <body>
        <div class="container">
            <div class="toolbar">
                <a href="/">&larr; Back to dashboard</a>
                <div class="refresh-toggle">
                    <label>
                        <input type="checkbox" id="auto-refresh-toggle" checked />
                        Auto refresh every 60s
                    </label>
                    <span class="last-refresh">Last refresh: <span id="last-refresh-label">--</span></span>
                </div>
            </div>
            <h1>Batch Details: {{ stats.filename }}</h1>
            <div class="grid">
                <div class="card"><span class="label">Total scanned</span>{{ stats.total }}</div>
                <div class="card"><span class="label">Passed</span>{{ stats.pass }}</div>
                <div class="card"><span class="label">Duplicate Scans</span>{{ stats.duplicate }}</div>
                <div class="card"><span class="label">Rejected</span>{{ stats.other }}</div>
                <div class="card"><span class="label">First scan</span>{{ stats.first_time or 'N/A' }}</div>
                <div class="card"><span class="label">Last scan</span>{{ stats.last_time or 'N/A' }}</div>
            </div>
            <h2>Hourly Breakdown</h2>
            <canvas id="timelineChart"></canvas>
        </div>
        <script>
            const timelineData = {{ chart_json | safe }};
            const ctx = document.getElementById('timelineChart');
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: timelineData.labels,
                    datasets: [
                        { label: 'Pass', data: timelineData.pass, borderColor:'#16a34a', backgroundColor:'rgba(22,163,74,0.2)', tension:0.3 },
                        { label: 'Duplicate', data: timelineData.duplicate, borderColor:'#f97316', backgroundColor:'rgba(249,115,22,0.2)', tension:0.3 },
                        { label: 'Other', data: timelineData.other, borderColor:'#1d4ed8', backgroundColor:'rgba(29,78,216,0.2)', tension:0.3 }
                    ]
                },
                options: {
                    responsive: true,
                    scales: {
                        y: { beginAtZero: true }
                    }
                }
            });
        </script>
    </body>
</html>
"""


TRENDS_TEMPLATE = """
<!doctype html>
<html lang="en">
    <head>
        <meta charset="utf-8" />
        <title>Batch Trends</title>
        {% if favicon_available %}
        <link rel="icon" type="image/png" href="{{ url_for('static', filename=favicon_filename) }}" />
        {% endif %}
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
        <style>
            body { font-family: "Segoe UI", Arial, sans-serif; background:#f8fafc; color:#1f2937; margin:0; padding:2rem; }
            a { color:#2563eb; text-decoration:none; }
            a:hover { text-decoration:underline; }
            .container { max-width:1080px; margin:0 auto; }
            h1 { color:#ff3b30; margin-bottom:1.5rem; }
            .chart-card { background:#ffffff; border-radius:12px; box-shadow:0 16px 40px -30px rgba(15,23,42,0.7); padding:1.5rem; margin-bottom:2rem; }
            .toolbar { display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:0.75rem; margin-bottom:1.2rem; }
            .refresh-toggle { color:#64748b; font-size:0.9rem; display:flex; flex-wrap:wrap; align-items:center; gap:0.75rem; }
            .last-refresh { font-weight:500; color:#475569; }
        </style>
        <script>
            const TRENDS_REFRESH_INTERVAL = 60000;
            const TRENDS_REFRESH_STORAGE_KEY = "batch_dashboard_autorefresh";

            function updateLastRefreshed(labelId) {
                const label = document.getElementById(labelId);
                if (!label) {
                    return;
                }
                label.textContent = new Date().toLocaleString();
            }

            function formatDateTime(date) {
                const day = String(date.getDate()).padStart(2, "0");
                const month = String(date.getMonth() + 1).padStart(2, "0");
                const year = date.getFullYear();
                const hours = String(date.getHours()).padStart(2, "0");
                const minutes = String(date.getMinutes()).padStart(2, "0");
                const seconds = String(date.getSeconds()).padStart(2, "0");
                return `${day}/${month}/${year} ${hours}:${minutes}:${seconds}`;
            }

            function updateLastRefreshed(labelId) {
                const label = document.getElementById(labelId);
                if (!label) {
                    return;
                }
                label.textContent = formatDateTime(new Date());
            }

            function initTrendsAutoRefresh() {
                const toggle = document.getElementById("auto-refresh-toggle");
                if (toggle) {
                    const stored = localStorage.getItem(TRENDS_REFRESH_STORAGE_KEY);
                    if (stored === "0") {
                        toggle.checked = false;
                    }
                    toggle.addEventListener("change", () => {
                        localStorage.setItem(TRENDS_REFRESH_STORAGE_KEY, toggle.checked ? "1" : "0");
                    });
                }
                updateLastRefreshed("last-refresh-label");
                setInterval(() => {
                    const enabled = !toggle || toggle.checked;
                    if (!enabled) {
                        return;
                    }
                    if (!document.hidden) {
                        window.location.reload();
                    }
                }, TRENDS_REFRESH_INTERVAL);
            }
            document.addEventListener("DOMContentLoaded", initTrendsAutoRefresh);
        </script>
    </head>
    <body>
        <div class="container">
            <div class="toolbar">
                <a href="/">&larr; Back to dashboard</a>
                <div class="refresh-toggle">
                    <label>
                        <input type="checkbox" id="auto-refresh-toggle" checked />
                        Auto refresh every 60s
                    </label>
                    <span class="last-refresh">Last refresh: <span id="last-refresh-label">--</span></span>
                </div>
            </div>
            <h1>Scan Trends</h1>
            <div class="chart-card">
                <h2>Daily Volume</h2>
                <canvas id="volumeChart"></canvas>
            </div>
            <div class="chart-card">
                <h2>Daily Pass / Duplicate</h2>
                <canvas id="qualityChart"></canvas>
            </div>
        </div>
        <script>
            const trendData = {{ trends_json | safe }};
            const volumeCtx = document.getElementById('volumeChart');
            new Chart(volumeCtx, {
                type: 'bar',
                data: {
                    labels: trendData.labels,
                    datasets: [
                        { label: 'Total scans', data: trendData.total, backgroundColor:'#2563eb' }
                    ]
                },
                options: { responsive:true, scales:{ y:{ beginAtZero:true } } }
            });

            const qualityCtx = document.getElementById('qualityChart');
            new Chart(qualityCtx, {
                type: 'line',
                data: {
                    labels: trendData.labels,
                    datasets: [
                        { label: 'Pass', data: trendData.pass, borderColor:'#16a34a', backgroundColor:'rgba(22,163,74,0.2)', tension:0.3 },
                        { label: 'Duplicate', data: trendData.duplicate, borderColor:'#f97316', backgroundColor:'rgba(249,115,22,0.2)', tension:0.3 }
                    ]
                },
                options: { responsive:true, scales:{ y:{ beginAtZero:true } } }
            });
        </script>
    </body>
</html>
"""


@app.route("/")
def index():
    batch_files = _list_csv(BATCH_LOG_DIR)
    scan_stats = _count_scans(batch_files)
    health = _health_metrics()
    return render_template_string(
        TEMPLATE,
        batch_files=batch_files,
        batch_count=len(batch_files),
        batch_total_size=_human_size(sum(f["size"] for f in batch_files) or 0.0),
        total_scans=scan_stats[0],
        total_pass=scan_stats[1],
        health=health,
        company_name=HEADER_TEXT,
        footer_text=FOOTER_TEXT,
        **_logo_context(),
    )


def _send_csv(directory: Path, filename: str):
    safe_name = Path(filename).name
    target = directory / safe_name
    if not target.exists() or target.suffix.lower() != ".csv":
        abort(404)
    download = request.args.get("download") == "1"
    return send_from_directory(directory, safe_name, as_attachment=download)


@app.route("/batch/<path:filename>")
def batch_file(filename: str):
    return _send_csv(BATCH_LOG_DIR, filename)


@app.route("/batch/<path:filename>/details")
def batch_details(filename: str):
    stats = _batch_stats(filename)
    chart_payload = {
        "labels": stats.pop("chart_labels"),
        "pass": stats.pop("chart_pass"),
        "duplicate": stats.pop("chart_duplicate"),
        "other": stats.pop("chart_other"),
    }
    return render_template_string(
        DETAIL_TEMPLATE,
        stats=stats,
        chart_json=json.dumps(chart_payload),
        **_logo_context(),
    )


@app.route("/trends")
def trends():
    batch_files = _list_csv(BATCH_LOG_DIR)
    aggregated = _daily_trends(batch_files)
    return render_template_string(
        TRENDS_TEMPLATE,
        trends_json=json.dumps(aggregated),
        **_logo_context(),
    )


if __name__ == "__main__":
    port = int(os.environ.get("LOG_VIEWER_PORT", "8080"))
    debug = os.environ.get("LOG_VIEWER_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=port, debug=debug)
