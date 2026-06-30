"""
auto_process.py - Autonomous screenshot correction processor.

Called by the compare server as a subprocess when corrections arrive.
Invokes Copilot CLI with the docs-screenshot skill to re-capture and
re-process each corrected screenshot, incorporating the user's feedback.

Writes progress to stdout (captured by the server for the /log endpoint)
and writes processing_done.flag when finished.

Usage:
    python lib/auto_process.py --corrections test-output/corrections.json
                               --pairs test-output/pairs.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parent))
sys.path.insert(0, str(_HERE))

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]


def log(msg: str) -> None:
    print(msg, flush=True)


def _find_copilot_exe() -> str | None:
    """Find the copilot CLI executable."""
    try:
        result = subprocess.run(
            ["where.exe", "copilot"] if sys.platform == "win32" else ["which", "copilot"],
            capture_output=True, text=True, timeout=5,
        )
        paths = result.stdout.strip().splitlines()
        for p in paths:
            p = p.strip()
            if p.endswith(".exe") or sys.platform != "win32":
                return p
        return paths[0].strip() if paths else None
    except Exception:
        return None


def apply_correction(
    correction: dict,
    pair: dict,
    pairs_path: str,
    copilot_exe: str,
) -> bool:
    """
    Invoke Copilot CLI with the docs-screenshot skill to re-capture
    a screenshot, incorporating the user's correction feedback.
    """
    image_name = correction["image"]
    suggestion = correction["suggestion"]
    article = pair.get("article", "")
    alt_text = pair.get("alt", "")
    cwd = Path.cwd()

    current_right = pair["right_path"]
    if not Path(current_right).is_absolute():
        current_right = str(cwd / current_right)

    # Determine output path (next version)
    stem = Path(current_right).stem
    base_stem = re.sub(r"-processed\d*$", "", stem)
    out_dir = Path(current_right).parent
    version = 2
    while True:
        candidate = out_dir / f"{base_stem}-processed{version}.png"
        if not candidate.exists():
            break
        version += 1
    output_path = str(candidate)
    log(f"  Output target: {Path(output_path).name}")

    prompt = (
        f'/docs-screenshot Recapture ONLY the screenshot "{image_name}" '
        f"for the article at {article}. "
        f'The screenshot alt text is: "{alt_text}". '
        f"\n\nThe reviewer gave this correction feedback:\n"
        f"{suggestion}\n\n"
        f"Use this feedback to improve how you capture and process the screenshot. "
        f"Save the final processed screenshot to: {output_path}\n"
        f"Use nogimp. Exit when done."
    )

    cmd = [
        copilot_exe,
        "-p", prompt,
        "--model", "claude-opus-4.6-1m",
        "--allow-all",
        "--effort", "high",
    ]
    log("  Invoking Copilot CLI (claude-opus-4.6-1m, high effort, all permissions)...")
    log("  This will take several minutes (browser automation + processing).")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env={**os.environ, "PYTHONUTF8": "1"},
        )
        for line in proc.stdout:  # type: ignore[union-attr]
            log(f"  [copilot] {line.rstrip()}")
        proc.wait()
        log(f"  Copilot exited with code {proc.returncode}")
    except Exception as exc:
        log(f"  ERROR invoking Copilot CLI: {exc}")
        return False

    if not Path(output_path).exists():
        log(f"  ERROR: Output file was not created: {output_path}")
        return False

    log(f"  Saved: {Path(output_path).name}")
    rel_output = str(Path(output_path).relative_to(cwd)).replace("\\", "/")
    pair["right_path"] = rel_output
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-process screenshot corrections.")
    parser.add_argument("--corrections", required=True)
    parser.add_argument("--pairs", required=True)
    args = parser.parse_args()

    corrections_path = args.corrections
    pairs_path = args.pairs
    pairs_dir = Path(pairs_path).parent
    flag_path = pairs_dir / "processing_done.flag"

    log("=" * 60)
    log("Auto-processor started")
    log(f"Corrections: {corrections_path}")
    log(f"Pairs: {pairs_path}")
    log("=" * 60)
    log("Each correction invokes the full docs-screenshot skill via Copilot CLI.")
    log("This includes browser automation, so expect several minutes per correction.")
    log("")

    copilot_exe = _find_copilot_exe()
    if not copilot_exe:
        log("FATAL: Could not find copilot CLI executable.")
        log("Ensure copilot is installed and on your PATH.")
        sys.exit(1)
    log(f"Copilot CLI: {copilot_exe}")

    with open(corrections_path, encoding="utf-8") as f:
        data = json.load(f)
    corrections = data.get("corrections", [])
    log(f"Found {len(corrections)} correction(s) to process.\n")

    with open(pairs_path, encoding="utf-8") as f:
        pairs = json.load(f)

    success_count = 0
    for i, correction in enumerate(corrections, 1):
        image_name = correction["image"]
        log(f"[{i}/{len(corrections)}] {image_name}")
        log(f"  Feedback: {correction['suggestion']}")

        pair = next((p for p in pairs if p["name"] == image_name), None)
        if pair is None:
            log(f"  WARNING: No pair found for '{image_name}' -- skipping.")
            continue

        ok = apply_correction(correction, pair, pairs_path, copilot_exe)
        if ok:
            success_count += 1
            log("  [OK] Done")
        else:
            log("  [FAIL] Keeping current image")

    log(f"\n{success_count}/{len(corrections)} correction(s) applied successfully.")

    # Save updated pairs.json
    with open(pairs_path, "w", encoding="utf-8") as f:
        json.dump(pairs, f, indent=2)
    log("Updated pairs.json saved.")

    # Write the flag to trigger server reload
    flag_path.write_text("done")
    log("processing_done.flag written -- server will reload report.")
    log("=" * 60)
    log("Auto-processor finished.")


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
