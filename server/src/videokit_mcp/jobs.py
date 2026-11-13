"""Background jobs. A render takes minutes, so tools start a job and return its id at once; the AI then polls
`job_status`. Each job is a list of shell-free steps run in order; state is saved to ~/.videokit/jobs/<id>/ so a
job survives a reconnect of the chat (not a restart of the server process, which marks running jobs as lost)."""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable

from . import config


@dataclass
class Step:
    label: str
    argv: list[str] | None = None      # a command to run (never through a shell)
    cwd: str | None = None
    env: dict[str, str] | None = None
    func: Callable[[], None] | None = None  # or Python work done in-process (e.g. collecting outputs)


@dataclass
class Job:
    id: str
    engine: str
    title: str
    status: str = "queued"           # queued | running | succeeded | failed | lost
    created: float = field(default_factory=time.time)
    started: float | None = None
    finished: float | None = None
    step: str = ""
    error: str = ""
    outputs: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    pid: int | None = None

    @property
    def dir(self) -> Path:
        return config.JOBS_DIR / self.id

    @property
    def log(self) -> Path:
        return self.dir / "log.txt"

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = self.dir / "job.json.tmp"
        tmp.write_text(json.dumps(asdict(self), indent=2))
        tmp.replace(self.dir / "job.json")

    def summary(self, log_lines: int = 0) -> dict:
        d = asdict(self)
        d.pop("pid")
        end = self.finished or time.time()
        d["seconds"] = round(end - self.started, 1) if self.started else 0
        if log_lines and self.log.exists():
            d["log_tail"] = _tail(self.log, log_lines)
        return d


def _tail(path: Path, n: int) -> str:
    with path.open("rb") as f:
        f.seek(0, os.SEEK_END)
        size = f.tell()
        f.seek(max(0, size - 64_000))
        lines = f.read().decode("utf-8", "replace").replace("\r", "\n").splitlines()
    # Renderers print a progress line per frame; keep the log readable for the AI.
    lines = [l for l in lines if l.strip() and "GL Driver Message" not in l]
    return "\n".join(lines[-n:])


_jobs: dict[str, Job] = {}
_lock = threading.Lock()


def start(engine: str, title: str, steps: list[Step], outputs: Callable[[], list[str]] | None = None,
          notes: list[str] | None = None) -> Job:
    job = Job(id=time.strftime("%Y%m%d-%H%M%S-") + secrets.token_hex(3), engine=engine, title=title,
              notes=list(notes or []))
    job.save()
    with _lock:
        _jobs[job.id] = job
    threading.Thread(target=_run, args=(job, steps, outputs), daemon=True).start()
    return job


def _run(job: Job, steps: list[Step], outputs: Callable[[], list[str]] | None) -> None:
    job.status, job.started = "running", time.time()
    job.save()
    try:
        with job.log.open("a", encoding="utf-8") as log:
            for s in steps:
                job.step = s.label
                job.save()
                log.write(f"\n=== {s.label}\n")
                log.flush()
                if s.func:
                    s.func()
                    continue
                assert s.argv
                log.write("$ " + " ".join(s.argv) + "\n")
                log.flush()
                p = subprocess.Popen(s.argv, cwd=s.cwd, env=config.job_env(s.env), stdout=log,
                                     stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL)
                job.pid = p.pid
                job.save()
                rc = p.wait()
                job.pid = None
                if rc != 0:
                    raise RuntimeError(f"step '{s.label}' exited with code {rc}; see log_tail")
        if outputs:
            job.outputs = outputs()
        job.status = "succeeded"
    except Exception as e:  # report every failure to the AI instead of crashing the server
        job.status, job.error = "failed", str(e)
    finally:
        job.finished, job.step = time.time(), ""
        job.save()


def get(job_id: str) -> Job:
    with _lock:
        if job_id in _jobs:
            return _jobs[job_id]
    f = config.JOBS_DIR / job_id / "job.json"
    if not f.exists() or "/" in job_id or ".." in job_id:
        raise KeyError(f"no job {job_id!r}")
    job = Job(**json.loads(f.read_text()))
    if job.status in ("queued", "running"):  # started by an earlier server process that is gone
        job.status, job.error = "lost", "the server restarted while this job ran; start it again"
        job.save()
    return job


def recent(limit: int = 20) -> list[Job]:
    if not config.JOBS_DIR.exists():
        return []
    ids = sorted((p.name for p in config.JOBS_DIR.iterdir() if (p / "job.json").exists()), reverse=True)
    out = []
    for i in ids[:limit]:
        try:
            out.append(get(i))
        except Exception:
            pass
    return out
