"""Streaming SSE endpoint for job progress and logs."""

from __future__ import annotations

import json
import logging
import queue
import re
import threading
import time
from collections.abc import Callable, Generator

from core.choices import JobStatusChoices
from django.http import Http404, HttpRequest, StreamingHttpResponse
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from netbox.jobs import Job as JobModel

logger = logging.getLogger(__name__)

SYNC_OWNER_RQ = "rq_job"

SYNC_WAIT_TIMEOUT = 60
SYNC_WAIT_POLL_INTERVAL = 0.5
JOB_CLASSIFICATION_GRACE_TIMEOUT = 1.0
JOB_CLASSIFICATION_GRACE_POLL_INTERVAL = 0.1
JOB_STREAM_HEARTBEAT_INTERVAL = 15.0
JOB_STREAM_PRODUCER_JOIN_TIMEOUT = 1.0
JOB_STREAM_HEARTBEAT = ": keep-alive\n\n"


def _job_data_mapping(job: JobModel) -> dict[str, object]:
    """Return job data as a mutable mapping, or an empty mapping if unusable."""
    data: object = getattr(job, "data", None)
    if isinstance(data, str):
        try:
            data = json.loads(data) if data else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return data if isinstance(data, dict) else {}


def _proxbox_sync_mapping(data: dict[str, object]) -> dict[str, object]:
    """Return the nested Proxbox sync object when it has the expected shape."""
    proxbox_sync = data.get("proxbox_sync")
    return proxbox_sync if isinstance(proxbox_sync, dict) else {}


def _claim_sync_ownership(job: JobModel, owner: str) -> bool:
    """Atomically claim sync ownership on a job. Returns True if claimed, False if already taken."""
    import datetime as dt

    data = _job_data_mapping(job)
    proxbox_sync = _proxbox_sync_mapping(data)
    current_owner = proxbox_sync.get("sync_owner")
    if current_owner and current_owner != owner:
        return False
    proxbox_sync["sync_owner"] = owner
    proxbox_sync["sync_owner_claimed_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    data["proxbox_sync"] = proxbox_sync
    job.data = data
    job.save(update_fields=["data"])
    return True


def _get_sync_ownership(job: JobModel) -> str | None:
    """Return the current sync owner for a job, or None if not claimed."""
    owner = _proxbox_sync_mapping(_job_data_mapping(job)).get("sync_owner")
    return owner if isinstance(owner, str) else None


def _is_proxbox_apply_job(job: JobModel) -> bool:
    data = getattr(job, "data", None)
    return isinstance(data, dict) and isinstance(data.get("proxbox_apply"), dict)


def _release_sync_ownership(job: JobModel, owner: str) -> None:
    """Release sync ownership if we are the owner."""
    data = _job_data_mapping(job)
    proxbox_sync = _proxbox_sync_mapping(data)
    if proxbox_sync.get("sync_owner") == owner:
        del proxbox_sync["sync_owner"]
        if proxbox_sync.get("sync_owner_claimed_at"):
            del proxbox_sync["sync_owner_claimed_at"]
        data["proxbox_sync"] = proxbox_sync
        job.data = data
        job.save(update_fields=["data"])


_STREAM_LOG_RE = re.compile(r"^\[proxbox-stream\]\s+(\S+):\s*(.+)$")


def _format_percent_template(message: str, args: object) -> str | None:
    """Best-effort percent-style formatting for persisted log templates."""
    if args in (None, (), [], {}):
        return message

    candidates: list[object] = []
    if isinstance(args, list):
        candidates.append(tuple(args))
    candidates.append(args)
    if not isinstance(args, (tuple, dict, list)):
        candidates.append((args,))

    for candidate in candidates:
        try:
            return message % candidate
        except Exception:  # pragma: no cover - defensive fallback
            continue
    return None


def _render_log_entry_message(entry: object) -> str | None:
    """Return the best available rendered message for a persisted log entry."""
    if not isinstance(entry, dict):
        return None

    message: str | None = None
    for key in ("rendered_message", "formatted_message", "message", "msg"):
        candidate = entry.get(key)
        if isinstance(candidate, str):
            message = candidate
            break
    if message is None:
        return None

    rendered = _format_percent_template(message, entry.get("args"))
    if rendered is not None:
        return rendered

    rendered = _format_percent_template(message, entry.get("arguments"))
    if rendered is not None:
        return rendered

    return message


def _decode_stream_log_entry(entry: object) -> tuple[str, dict[str, object]] | None:
    """Decode persisted ``[proxbox-stream] ...`` log entries into SSE frames."""
    if not isinstance(entry, dict):
        return None
    raw = _render_log_entry_message(entry)
    if raw is None:
        return None
    match = _STREAM_LOG_RE.match(raw.strip())
    if not match:
        return None
    event = match.group(1).strip() or "message"
    payload_raw = match.group(2).strip()
    if not payload_raw:
        return event, {"message": ""}
    try:
        payload = json.loads(payload_raw)
    except json.JSONDecodeError:
        return event, {"raw": payload_raw}
    if isinstance(payload, dict):
        return event, payload
    return event, {"raw": payload}


def _wait_for_job_status(
    job: JobModel,
    target_status: str,
    timeout: float = SYNC_WAIT_TIMEOUT,
    poll_interval: float = SYNC_WAIT_POLL_INTERVAL,
    stop_event: threading.Event | None = None,
) -> str:
    """Wait for job to reach target status, returning the final status."""
    start = time.monotonic()
    job.refresh_from_db()
    current = getattr(job, "status", None)
    while current != target_status:
        if current in JobStatusChoices.TERMINAL_STATE_CHOICES:
            return current
        elapsed = time.monotonic() - start
        if elapsed >= timeout:
            logger.warning(
                "Timed out waiting for job %s to reach status %s (current: %s, elapsed: %.1fs)",
                getattr(job, "pk", "?"),
                target_status,
                current,
                elapsed,
            )
            return current
        if stop_event is not None:
            if stop_event.wait(poll_interval):
                return current
        else:
            time.sleep(poll_interval)
        job.refresh_from_db()
        current = getattr(job, "status", None)
    return current


def _wait_for_observable_job(
    job: JobModel,
    is_sync_job: Callable[[JobModel], bool],
    timeout: float = JOB_CLASSIFICATION_GRACE_TIMEOUT,
    poll_interval: float = JOB_CLASSIFICATION_GRACE_POLL_INTERVAL,
    stop_event: threading.Event | None = None,
) -> tuple[bool, bool]:
    """Wait briefly for asynchronously persisted Proxbox job metadata."""
    start = time.monotonic()
    while True:
        job.refresh_from_db()
        is_apply_job = _is_proxbox_apply_job(job)
        if is_sync_job(job) or is_apply_job:
            return True, is_apply_job
        status = getattr(job, "status", None)
        if status not in JobStatusChoices.ENQUEUED_STATE_CHOICES:
            return False, is_apply_job
        remaining = timeout - (time.monotonic() - start)
        if remaining <= 0:
            return False, is_apply_job
        wait_duration = min(poll_interval, remaining)
        if stop_event is not None:
            if stop_event.wait(wait_duration):
                return False, is_apply_job
        else:
            time.sleep(wait_duration)


def _queued_wait_outcome(
    status: object,
) -> tuple[str, bool, str, str | None] | None:
    """Describe a queued wait that did not end in the running state."""
    if status == JobStatusChoices.STATUS_RUNNING:
        return None
    if status in JobStatusChoices.TERMINAL_STATE_CHOICES:
        terminal_status = str(status)
        return (
            terminal_status,
            status == JobStatusChoices.STATUS_COMPLETED,
            f"Job finished with status {terminal_status}",
            None,
        )
    queued_status = str(status or "unknown")
    message = f"Job is still {queued_status}; waiting for a worker."
    return "waiting", False, message, "waiting"


def _iter_job_log_events(
    log_entries: list[object], start_index: int
) -> Generator[tuple[str, dict[str, object]], None, None]:
    """Yield observable SSE events from newly persisted job log entries."""
    for entry in log_entries[start_index:]:
        decoded = _decode_stream_log_entry(entry)
        if decoded is not None:
            event_name, payload = decoded
            if event_name != "complete":
                yield event_name, payload
            continue
        message = _render_log_entry_message(entry)
        if isinstance(message, str) and message.strip():
            yield (
                "message",
                {
                    "step": "job",
                    "status": "progress",
                    "message": message,
                },
            )


def _job_log_entries(job: JobModel) -> list[object]:
    """Return persisted log entries when NetBox exposes the expected list shape."""
    log_entries = getattr(job, "log_entries", None)
    return log_entries if isinstance(log_entries, list) else []


def _emit_job_log_events(
    job: JobModel,
    start_index: int,
    emit: Callable[[str, dict[str, object]], None],
) -> int:
    """Emit newly persisted job logs and return the consumed entry count."""
    log_entries = _job_log_entries(job)
    for event_name, payload in _iter_job_log_events(log_entries, start_index):
        emit(event_name, payload)
    return len(log_entries)


@method_decorator(csrf_exempt, name="dispatch")
class JobStreamSSEView(View):
    """Stream SSE for job status, progress, and live log entries."""

    http_method_names = ["get"]

    def get(self, request: HttpRequest, pk: int) -> StreamingHttpResponse:
        """Handle get."""
        job = JobModel.objects.filter(pk=pk).first()
        if not job:
            raise Http404("Job not found")

        return StreamingHttpResponse(
            self._stream_job_events(job),
            content_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache, no-transform",
                "X-Accel-Buffering": "no",
            },
        )

    def _stream_job_events(self, job: JobModel) -> Generator[str, None, None]:
        from netbox_proxbox.jobs import is_proxbox_sync_job

        event_queue: queue.Queue[object] = queue.Queue()
        queue_sentinel = object()
        stop_event = threading.Event()

        def emit(event: str, payload: dict[str, object]) -> None:
            event_queue.put(self._serialize_sse(event, payload))

        def emit_error(message: str) -> None:
            emit(
                "error",
                {"step": "job", "status": "failed", "message": message},
            )

        def emit_complete(ok: bool, message: str, *, status: str | None = None) -> None:
            payload: dict[str, object] = {"ok": ok, "message": message}
            if status is not None:
                payload["status"] = status
            emit("complete", payload)

        def worker() -> None:
            from django.db import close_old_connections

            close_old_connections()
            try:
                is_observable_job, is_apply_job = _wait_for_observable_job(
                    job,
                    is_proxbox_sync_job,
                    stop_event=stop_event,
                )
                if stop_event.is_set():
                    return
                if not is_observable_job:
                    emit_error("Not a Proxbox sync or apply job")
                    emit_complete(False, "Not a Proxbox sync or apply job")
                    return

                status = getattr(job, "status", None)

                if status in JobStatusChoices.TERMINAL_STATE_CHOICES:
                    _emit_job_log_events(job, 0, emit)
                    emit(
                        "step",
                        {
                            "step": "job",
                            "status": status,
                            "message": f"Job is already {status}",
                        },
                    )
                    emit_complete(
                        status == JobStatusChoices.STATUS_COMPLETED,
                        f"Job is already {status}",
                    )
                    return

                if status in (
                    JobStatusChoices.STATUS_PENDING,
                    JobStatusChoices.STATUS_SCHEDULED,
                ):
                    emit(
                        "step",
                        {
                            "step": "job",
                            "status": "waiting",
                            "message": f"Job is {status}, waiting for worker to start...",
                        },
                    )
                    status = _wait_for_job_status(
                        job,
                        JobStatusChoices.STATUS_RUNNING,
                        stop_event=stop_event,
                    )
                    if stop_event.is_set():
                        return
                    queued_outcome = _queued_wait_outcome(status)
                    if queued_outcome is not None:
                        step_status, ok, message, complete_status = queued_outcome
                        _emit_job_log_events(job, 0, emit)
                        emit(
                            "step",
                            {
                                "step": "job",
                                "status": step_status,
                                "message": message,
                            },
                        )
                        emit_complete(ok, message, status=complete_status)
                        return

                sync_owner = _get_sync_ownership(job)
                emit(
                    "step",
                    {
                        "step": "job",
                        "status": "started",
                        "message": (
                            "Observing Proxbox apply job progress"
                            if is_apply_job
                            else "Observing Proxbox sync job progress"
                            if not sync_owner
                            else f"Observing Proxbox sync handled by {sync_owner}"
                        ),
                    },
                )

                last_status = status
                emitted_terminal = False
                seen_log_entries = 0

                while not stop_event.is_set():
                    job.refresh_from_db()
                    current_status = getattr(job, "status", None)

                    if current_status != last_status:
                        emit(
                            "step",
                            {
                                "step": "job",
                                "status": current_status,
                                "message": f"Job status changed to {current_status}",
                            },
                        )
                        last_status = current_status

                    seen_log_entries = _emit_job_log_events(job, seen_log_entries, emit)

                    if current_status in JobStatusChoices.TERMINAL_STATE_CHOICES:
                        ok = current_status == JobStatusChoices.STATUS_COMPLETED
                        emit_complete(ok, f"Job finished with status {current_status}")
                        emitted_terminal = True
                        break

                    if stop_event.wait(SYNC_WAIT_POLL_INTERVAL):
                        break

                if not emitted_terminal and not stop_event.is_set():
                    emit_complete(False, "Job stream ended unexpectedly")
            except Exception as exc:  # pragma: no cover - defensive stream guard
                logger.exception(
                    "Unexpected error streaming job %s", getattr(job, "pk", "?")
                )
                emit_error(f"Job stream failed unexpectedly: {exc}")
                emit_complete(False, "Job stream failed unexpectedly.")
            finally:
                close_old_connections()
                event_queue.put(queue_sentinel)

        stream_thread = threading.Thread(target=worker, daemon=True)
        stream_thread.start()

        try:
            while True:
                try:
                    item = event_queue.get(timeout=JOB_STREAM_HEARTBEAT_INTERVAL)
                except queue.Empty:
                    yield JOB_STREAM_HEARTBEAT
                    continue
                if item is queue_sentinel:
                    break
                yield str(item)
        finally:
            stop_event.set()
            stream_thread.join(timeout=JOB_STREAM_PRODUCER_JOIN_TIMEOUT)
            if stream_thread.is_alive():
                logger.warning(
                    "Job stream producer for job %s did not stop within %.1fs",
                    getattr(job, "pk", "?"),
                    JOB_STREAM_PRODUCER_JOIN_TIMEOUT,
                )

    def _serialize_sse(self, event: str, payload: dict[str, object]) -> str:
        return f"event: {event}\ndata: {json.dumps(payload)}\n\n"
