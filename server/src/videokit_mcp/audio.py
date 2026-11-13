"""Sound for any engine: beat grids (librosa), offline narration (Kokoro), mixing and loudness mastering (ffmpeg),
licensed sound effects (Freesound via video-shotcraft's script) and a credits file for the video description."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import urllib.request
from pathlib import Path

from . import config, jobs, vendor

KOKORO_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
KOKORO_FILES = ("kokoro-v1.0.onnx", "voices-v1.0.bin")


class AudioError(ValueError):
    pass


# -- beats ---------------------------------------------------------------------------------------------------------
def beats(path: Path, max_beats: int = 400) -> dict:
    import librosa
    import numpy as np

    y, sr = librosa.load(str(path), sr=22050, mono=True)
    dur = len(y) / sr
    tempo, frames = librosa.beat.beat_track(y=y, sr=sr)
    times = librosa.frames_to_time(frames, sr=sr)
    tempo = float(np.atleast_1d(tempo)[0])
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    # Strong accents: the loudest onsets, a useful list of "hit" moments for cuts and impacts.
    peaks = librosa.util.peak_pick(onset_env, pre_max=7, post_max=7, pre_avg=20, post_avg=20, delta=0.5, wait=10)
    strong = sorted(peaks, key=lambda i: -onset_env[i])[:24]
    rms = librosa.feature.rms(y=y)[0]
    rms_t = librosa.frames_to_time(np.arange(len(rms)), sr=sr)
    step = max(1, len(rms) // 60)  # an energy curve of ~60 points, for building intensity
    return {
        "file": str(path), "seconds": round(dur, 3), "tempo_bpm": round(tempo, 2),
        "beat_count": int(len(times)), "beats": [round(float(t), 3) for t in times[:max_beats]],
        "bars_every_4_beats": [round(float(t), 3) for t in times[::4][:max_beats // 4]],
        "accents": sorted(round(float(librosa.frames_to_time(i, sr=sr)), 3) for i in strong),
        "energy": [[round(float(rms_t[i]), 2), round(float(rms[i] / (rms.max() or 1)), 3)]
                   for i in range(0, len(rms), step)],
        "note": "Beat times are estimates: snap cuts to them, then check the result by ear and with look().",
    }


# -- narration -----------------------------------------------------------------------------------------------------
def _kokoro_dir() -> Path:
    return config.CACHE_DIR / "kokoro"


def _ensure_kokoro() -> None:
    d = _kokoro_dir()
    d.mkdir(parents=True, exist_ok=True)
    for f in KOKORO_FILES:
        if not (d / f).exists():
            tmp = d / (f + ".part")
            with urllib.request.urlopen(KOKORO_URL + f, timeout=600) as r, tmp.open("wb") as out:
                shutil.copyfileobj(r, out, 1 << 20)
            tmp.replace(d / f)


def narrate(lines: list[dict], out_dir: Path) -> jobs.Job:
    """One WAV per line (Kokoro, offline; ~350 MB model downloaded on first use) + durations.json."""
    if not lines:
        raise AudioError("lines is empty")
    for i, line in enumerate(lines):
        if not str(line.get("text", "")).strip():
            raise AudioError(f"line {i} has no text")
        if re.search(r"[぀-ヿ㐀-鿿가-힯]", line["text"]) and \
                not str(line.get("lang", "en-us")).lower().startswith(("cmn", "zh", "ja")):
            raise AudioError(f"line {i} has Chinese/Japanese/Korean text: set lang 'cmn' (or 'ja') and a matching voice")
    out_dir.mkdir(parents=True, exist_ok=True)

    def synth() -> None:
        import soundfile as sf
        from kokoro_onnx import Kokoro

        k = Kokoro(str(_kokoro_dir() / KOKORO_FILES[0]), str(_kokoro_dir() / KOKORO_FILES[1]))
        voices = set(k.get_voices())
        durations = {}
        for i, line in enumerate(lines):
            lang = line.get("lang", "en-us")
            voice = line.get("voice") or ("zf_xiaoxiao" if lang == "cmn" else "af_bella")
            if voice not in voices:
                raise AudioError(f"unknown voice {voice!r}; voices: {sorted(voices)}")
            samples, sr = k.create(line["text"], voice=voice, speed=float(line.get("speed", 0.95)), lang=lang)
            name = f"{line.get('id', i):0>3}.wav" if str(line.get("id", i)).isdigit() else f"{line['id']}.wav"
            sf.write(out_dir / name, samples, sr)
            durations[name] = round(len(samples) / sr, 3)
        (out_dir / "durations.json").write_text(json.dumps(durations, indent=2))

    return jobs.start("audio", f"narrate {len(lines)} line(s)", [
        jobs.Step("download Kokoro voice model (first use only, ~350 MB)", func=_ensure_kokoro),
        jobs.Step("synthesize", func=synth),
    ], lambda: sorted(str(p) for p in out_dir.glob("*.wav")) + [str(out_dir / "durations.json")],
        notes=["Kokoro (Apache-2.0 weights): fine for monetized videos. Voices: af_*/am_* American, bf_*/bm_* British."])


# -- mixing and mastering -----------------------------------------------------------------------------------------
def _duration(path: Path) -> float:
    r = subprocess.run([config.ffprobe(), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                        str(path)], capture_output=True, text=True, timeout=60)
    try:
        return float(r.stdout.strip())
    except ValueError:
        raise AudioError(f"cannot read {path}: {r.stderr.strip()[:200]}") from None


def mux(video: Path, tracks: list[dict], out: Path, lufs: float = -14.0, true_peak: float = -1.5) -> dict:
    """Mix tracks [{path, start=0, volume=1.0}] under the video, master to `lufs` (YouTube plays at -14) with a
    two-pass loudnorm, pad or cut to the picture's length, copy the picture untouched."""
    if not video.exists():
        raise AudioError(f"not found: {video}")
    if not tracks:
        raise AudioError("tracks is empty")
    vdur = _duration(video)
    ins, chains = [], []
    for i, t in enumerate(tracks):
        p = Path(t["path"]).expanduser().resolve()
        if not p.exists():
            raise AudioError(f"not found: {p}")
        ins += ["-i", str(p)]
        ms = int(float(t.get("start", 0)) * 1000)
        chains.append(f"[{i + 1}:a]aformat=sample_rates=48000:channel_layouts=stereo,"
                      f"volume={float(t.get('volume', 1.0))},adelay={ms}|{ms}[t{i}]")
    mixed = "".join(f"[t{i}]" for i in range(len(tracks)))
    pre = ";".join(chains) + f";{mixed}amix=inputs={len(tracks)}:normalize=0:dropout_transition=0,apad,atrim=0:{vdur:.3f}"
    target = f"I={lufs}:TP={true_peak}:LRA=11"
    # pass 1: measure
    r = subprocess.run([config.ffmpeg(), "-hide_banner", "-nostats", "-f", "lavfi", "-i", "anullsrc", *ins,
                        "-filter_complex", pre + f",loudnorm={target}:print_format=json[o]", "-map", "[o]",
                        "-f", "null", "-"], capture_output=True, text=True, timeout=1800)
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr)
    if r.returncode != 0 or not m:
        raise AudioError("loudness measurement failed: " + r.stderr.strip()[-400:])
    meas = json.loads(m.group(0))
    if meas["input_i"] in ("-inf", "inf"):
        raise AudioError("the mixed audio is silent")
    ln = (f"loudnorm={target}:measured_I={meas['input_i']}:measured_TP={meas['input_tp']}:"
          f"measured_LRA={meas['input_lra']}:measured_thresh={meas['input_thresh']}:offset={meas['target_offset']}:"
          f"linear=true")
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".part" + out.suffix)
    r = subprocess.run([config.ffmpeg(), "-hide_banner", "-v", "error", "-y", "-i", str(video), *ins,
                        "-filter_complex", pre + f",{ln},aresample=48000[a]", "-map", "0:v:0", "-map", "[a]",
                        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", f"{vdur:.3f}", "-movflags", "+faststart",
                        str(tmp)], capture_output=True, text=True, timeout=1800)
    if r.returncode != 0:
        tmp.unlink(missing_ok=True)
        raise AudioError("mux failed: " + r.stderr.strip()[-400:])
    tmp.replace(out)
    return {"out": str(out), "seconds": round(vdur, 3), "target_lufs": lufs, "measured_input_lufs": meas["input_i"],
            "tracks": len(tracks)}


# -- sound effects ------------------------------------------------------------------------------------------------
def sound_effects(action: str, query: str, ids: list[str], license: str, max_duration: float | None,
                  out_dir: Path | None, limit: int) -> dict:
    try:
        script = vendor.fetch_now("video-shotcraft") / "assets" / "scripts" / "sfx-source.py"
    except RuntimeError as e:
        raise AudioError(str(e)) from None
    if license not in ("cc0", "by"):
        raise AudioError("license must be 'cc0' (no credit needed) or 'by' (CC0 + CC BY, credit needed)")
    if action == "search":
        if not query:
            raise AudioError("search needs a query, e.g. 'paper slide' or 'short cinematic impact'")
        argv = [config.python(), "-I", str(script), "search", query, "--license", license, "--limit", str(limit)]
        if max_duration:
            argv += ["--max-duration", str(max_duration)]
    elif action == "get":
        if not ids or not out_dir:
            raise AudioError("get needs ids (from search) and out_dir (e.g. <project>/public/audio/sfx)")
        out_dir.mkdir(parents=True, exist_ok=True)
        argv = [config.python(), "-I", str(script), "get", *map(str, ids), "--out-dir", str(out_dir),
                "--license", license]
    else:
        raise AudioError("action must be 'search' or 'get'")
    r = subprocess.run(argv, capture_output=True, text=True, timeout=300, env=config.job_env())
    if r.returncode != 0:
        msg = (r.stderr or r.stdout).strip()[-500:]
        if "403" in msg:
            msg += (" | Freesound refused the request. From a cloud session this usually means Freesound blocks "
                    "that network; it works from your own computer.")
        raise AudioError(msg)
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        data = {"output": r.stdout.strip()[-3000:]}
    return {"action": action, "license": license, "result": data,
            "credits_file": str(out_dir / "FREESOUND-CREDITS.md") if action == "get" and out_dir else None}


# -- credits -------------------------------------------------------------------------------------------------------
_UNVERIFIED = ("keyboard.mp3", "riser-cine.mp3", "sparkle.mp3", "whoosh-big.mp3", "pop.mp3")


def write_credits(project_dir: Path, items: list[dict]) -> dict:
    """CREDITS.md for the project (and a short block to paste into a video description). Collects the credits
    files tools wrote (Freesound, lemo CREDITS) and the items you pass: [{what, title, author, license, url}]."""
    lines = ["# Credits", ""]
    desc: list[str] = []
    for it in items:
        bits = [it.get("title") or it.get("what", "")]
        if it.get("author"):
            bits.append(f"by {it['author']}")
        if it.get("license"):
            bits.append(f"({it['license']})")
        if it.get("url"):
            bits.append(it["url"])
        lines.append(f"- {it.get('what', 'asset')}: " + " ".join(b for b in bits if b))
        if (it.get("license") or "").upper() not in ("CC0", "PUBLIC DOMAIN", "MIXKIT", ""):
            desc.append(" ".join(b for b in bits if b))
    found = []
    for f in sorted(project_dir.rglob("FREESOUND-CREDITS.md")) + sorted(project_dir.rglob("CREDITS")):
        if "node_modules" in f.parts:
            continue
        found.append(str(f))
        text = f.read_text(encoding="utf-8", errors="replace").strip()
        lines += ["", f"## From {f.relative_to(project_dir)}", "", text]
        desc += [l.strip("- ").strip() for l in text.splitlines() if "CC BY" in l and "NC" not in l]
    warnings = []
    for n in _UNVERIFIED:
        if any(p.name == n for p in project_dir.rglob(n) if "node_modules" not in p.parts):
            warnings.append(f"{n}: template sound effect with no recorded source; replace it before monetizing")
    if (project_dir / "src" / "clawd.js").exists():
        warnings.append("src/clawd.js is present: Clawd is Anthropic's character; do not publish or monetize a "
                        "video that shows it")
    lines += ["", "## Tools", "", "- Made with videokit (code-rendered animation)."]
    out = project_dir / "CREDITS.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return {"credits_file": str(out), "collected_from": found, "warnings": warnings,
            "description_block": ("Credits:\n" + "\n".join(f"- {d}" for d in desc)) if desc else
            "No attribution is required for the listed assets."}
