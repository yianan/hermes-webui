"""Local Gmail watcher controls for Hermes WebUI.

Gateway lifecycle is owned by the upstream WebUI. This module retains only the
watcher-specific status and Hermes CLI cron operations needed by the local UI.
It never accepts arbitrary commands from the browser.
"""

from __future__ import annotations

import os
import json
import subprocess
from pathlib import Path
from typing import Any


HOME = Path.home()
HERMES_BIN = HOME / ".local" / "bin" / "hermes"
GMAIL_WATCHER_NAME = "Gmail Keyword Watcher"
GMAIL_WATCHER_SCRIPT = "gmail_keyword_watcher.py"


def _active_hermes_home() -> Path:
    try:
        from api.profiles import get_active_hermes_home

        return Path(get_active_hermes_home()).expanduser().resolve()
    except Exception:
        return Path(os.getenv("HERMES_HOME", str(HOME / ".hermes"))).expanduser().resolve()


def _active_agent_dir() -> Path:
    try:
        from api.config import _AGENT_DIR

        if _AGENT_DIR is not None:
            return Path(_AGENT_DIR).expanduser().resolve()
    except Exception:
        pass
    return _active_hermes_home() / "hermes-agent"


def _watcher_config_path() -> Path:
    return _active_hermes_home() / "scripts" / "gmail_keyword_watcher.json"


def _watcher_seen_path() -> Path:
    return _active_hermes_home() / "scripts" / "state" / "gmail_keyword_seen.txt"


def _watcher_log_path() -> Path:
    return _active_hermes_home() / "logs" / "gmail-keyword-watcher.log"


def _watcher_session_path() -> Path:
    state_dir = Path(
        os.getenv("HERMES_WEBUI_STATE_DIR", str(_active_hermes_home() / "webui"))
    ).expanduser().resolve()
    return state_dir / "sessions" / "gmail_keyword_watcher.json"


def _gateway_status_module():
    import importlib

    return importlib.import_module("gateway.status")


def _running_pid() -> int | None:
    try:
        status_mod = _gateway_status_module()
        try:
            pid = status_mod.get_running_pid(cleanup_stale=False)
        except TypeError:
            pid = status_mod.get_running_pid()
        return int(pid) if pid is not None else None
    except Exception:
        pass
    return _running_gateway_pid_from_process_table()


def _gateway_running() -> bool:
    """Use Hermes' built-in gateway status, with a process-table fallback."""
    return _running_pid() is not None


def _running_gateway_pid_from_process_table() -> int | None:
    try:
        proc = subprocess.run(
            ["ps", "-axo", "pid=,command="],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=4.0,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    for line in proc.stdout.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            pid_text, command = stripped.split(None, 1)
        except ValueError:
            continue
        if "hermes gateway run" in command and "rg " not in command:
            try:
                return int(pid_text)
            except ValueError:
                return None
    return None


def _tail(path: Path, max_lines: int = 24, max_bytes: int = 16_384) -> list[str]:
    try:
        if not path.exists():
            return []
        with path.open("rb") as fh:
            try:
                fh.seek(max(0, path.stat().st_size - max_bytes))
            except OSError:
                pass
            text = fh.read().decode("utf-8", errors="replace")
        return text.splitlines()[-max_lines:]
    except Exception:
        return []


def _run_cli(args: list[str], timeout: float = 20.0) -> dict[str, Any]:
    if not HERMES_BIN.exists():
        return {
            "ok": False,
            "returncode": 127,
            "stdout": "",
            "stderr": f"Hermes CLI not found at {HERMES_BIN}",
        }
    env = os.environ.copy()
    env["HERMES_HOME"] = str(_active_hermes_home())
    agent_dir = _active_agent_dir()
    try:
        proc = subprocess.run(
            [str(HERMES_BIN), *args],
            cwd=str(agent_dir if agent_dir.exists() else HOME),
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "returncode": None,
            "stdout": (exc.stdout or "")[-4000:] if isinstance(exc.stdout, str) else "",
            "stderr": "Timed out while running hermes " + " ".join(args),
        }


def _cron_jobs_path() -> Path:
    return _active_hermes_home() / "cron" / "jobs.json"


def _load_cron_jobs() -> list[dict[str, Any]]:
    path = _cron_jobs_path()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    jobs = payload.get("jobs") if isinstance(payload, dict) else []
    return [job for job in jobs if isinstance(job, dict)] if isinstance(jobs, list) else []


def _gmail_watcher_job() -> dict[str, Any] | None:
    for job in _load_cron_jobs():
        if job.get("script") == GMAIL_WATCHER_SCRIPT or job.get("name") == GMAIL_WATCHER_NAME:
            return job
    return None


def _count_lines(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for line in handle if line.strip())
    except Exception:
        return 0


def _gmail_watcher_recent_alerts(limit: int = 3) -> list[dict[str, Any]]:
    session_path = _watcher_session_path()
    try:
        payload = json.loads(session_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    messages = payload.get("messages") if isinstance(payload, dict) else []
    if not isinstance(messages, list):
        return []
    alerts: list[dict[str, Any]] = []
    for message in reversed(messages):
        if not isinstance(message, dict):
            continue
        content = str(message.get("content") or "").strip()
        if not content:
            continue
        alerts.append(
            {
                "role": message.get("role") or "assistant",
                "timestamp": message.get("timestamp"),
                "content": content,
            }
        )
        if len(alerts) >= limit:
            break
    return alerts


def gmail_watcher_status() -> dict[str, Any]:
    job = _gmail_watcher_job()
    enabled = bool(job and job.get("enabled", True) and job.get("state") != "paused")
    config_path = _watcher_config_path()
    seen_path = _watcher_seen_path()
    log_path = _watcher_log_path()
    status = {
        "service": "gmail_watcher",
        "configured": job is not None,
        "running": enabled,
        "scheduler_running": _gateway_running(),
        "job": job,
        "job_id": job.get("id") if job else None,
        "name": job.get("name") if job else GMAIL_WATCHER_NAME,
        "state": job.get("state") if job else "missing",
        "enabled": enabled,
        "schedule": job.get("schedule_display") if job else None,
        "deliver": job.get("deliver") if job else None,
        "next_run_at": job.get("next_run_at") if job else None,
        "last_run_at": job.get("last_run_at") if job else None,
        "last_status": job.get("last_status") if job else None,
        "last_error": job.get("last_error") if job else None,
        "last_delivery_error": job.get("last_delivery_error") if job else None,
        "completed": ((job.get("repeat") or {}).get("completed") if job else None),
        "config_path": str(config_path),
        "seen_path": str(seen_path),
        "seen_count": _count_lines(seen_path),
        "webui_session_id": "gmail_keyword_watcher",
        "recent_alerts": _gmail_watcher_recent_alerts(),
        "log_path": str(log_path),
        "log_tail": _tail(log_path, max_lines=18),
    }
    if not status["configured"]:
        status["hint"] = "Create the job with hermes cron create \"every 1m\" --name \"Gmail Keyword Watcher\" --script gmail_keyword_watcher.py --no-agent --deliver slack:C0B0599H2MB"
    return status


def gmail_watcher_control(action: str) -> dict[str, Any]:
    action = str(action or "").strip().lower()
    before = gmail_watcher_status()
    job_id = before.get("job_id")
    if not job_id:
        return {
            "ok": False,
            "action": action,
            "error": "Gmail Keyword Watcher cron job is not configured",
            "status": before,
        }
    if action == "start":
        cli = _run_cli(["cron", "resume", str(job_id)], timeout=12.0)
    elif action == "stop":
        cli = _run_cli(["cron", "pause", str(job_id)], timeout=12.0)
    elif action == "run":
        cli = _run_cli(["cron", "run", str(job_id)], timeout=12.0)
    else:
        return {"ok": False, "action": action, "error": f"Unknown watcher action: {action}", "status": before}
    status = gmail_watcher_status()
    return {
        "ok": bool(cli.get("ok")),
        "action": action,
        "changed": bool(cli.get("ok")),
        "cli": cli,
        "status": status,
    }
