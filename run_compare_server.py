#!/usr/bin/env python3
"""
run_compare_server.py - Start the interactive comparison review server.

Reads pairs from a JSON file, starts the CompareServer, generates the
comparison report HTML, serves it, and waits for feedback. When the user
submits corrections, saves them to corrections.json. When the user
finalizes (no corrections), creates a PR.

Usage:
    python run_compare_server.py --pairs test-output/pairs.json [--title "My Report"]

The script prints the server URL to stdout so the caller can open it.
When feedback or corrections arrive, it prints them to stdout and exits.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import sys
import webbrowser
from pathlib import Path

# Allow running from repo root or lib/ directory
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE))
sys.path.insert(0, str(_HERE / "lib"))

from lib.local_server import CompareServer
from lib.comparison_report import generate_comparison_report


def _load_pairs(pairs_path: str) -> list[dict]:
    with open(pairs_path, encoding="utf-8") as f:
        return json.load(f)


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the comparison review server.")
    parser.add_argument("--pairs", required=True, help="Path to pairs JSON file")
    parser.add_argument("--title", default="Screenshot Comparison", help="Report title")
    parser.add_argument("--subtitle", default="", help="Report subtitle")
    parser.add_argument("--output", default=None, help="Save HTML report to this path")
    parser.add_argument("--start-iteration", type=int, default=0,
                        help="Start at this iteration number (e.g. 1 after corrections have been processed offline)")
    parser.add_argument("--resource-group", default="",
                        help="Azure resource group to tear down after review (leave empty to skip teardown)")
    parser.add_argument("--no-teardown", action="store_true",
                        help="Skip automatic resource teardown after PR creation or dismiss")
    args = parser.parse_args()

    pairs = _load_pairs(args.pairs)
    if not pairs:
        print("ERROR: No pairs found in pairs JSON.", flush=True)
        sys.exit(1)

    corrections_path = str(Path(args.pairs).parent / "corrections.json")
    flag_path = Path(args.pairs).parent / "processing_done.flag"

    # Start server with empty HTML (will be updated immediately)
    server = CompareServer()
    server.corrections_path = corrections_path
    server.pairs_path = args.pairs
    server.start()
    port = server._port

    print(f"COMPARE_SERVER_URL=http://127.0.0.1:{port}", flush=True)
    print(f"COMPARE_SERVER_PORT={port}", flush=True)

    # Generate the report now that we know the port
    html = generate_comparison_report(
        pairs=pairs,
        title=args.title,
        subtitle=args.subtitle,
        output_path=args.output,
        embed_images=True,
        server_port=port,
        iteration=args.start_iteration,
    )
    server.update_report(html)
    print(f"REPORT_READY: Serving {len(pairs)} screenshot pair(s) at http://127.0.0.1:{port}", flush=True)

    # Auto-open the browser so the user doesn't have to copy/paste the URL
    webbrowser.open(f"http://127.0.0.1:{port}")

    # Handle SIGINT gracefully
    def _shutdown(sig, frame):
        print("\nShutting down server...", flush=True)
        server.stop()
        sys.exit(0)
    signal.signal(signal.SIGINT, _shutdown)

    # Main feedback loop
    iteration = args.start_iteration
    while True:
        print(f"WAITING_FOR_FEEDBACK (iteration {iteration})", flush=True)
        try:
            feedback = server.wait_for_feedback(timeout=None)
        except TimeoutError:
            print("TIMEOUT: Exiting.", flush=True)
            server.stop()
            sys.exit(0)

        if feedback == "dismiss":
            # User confirmed no changes needed — tear down resources
            print("DISMISS_REQUESTED", flush=True)
            _teardown_resources(server, args)
            break
        elif feedback is None:
            # User finalized — create PR
            print("FINALIZE_REQUESTED", flush=True)
            _create_pr(server, pairs, args)
            break
        elif not feedback and iteration == 0:
            # Iteration 0, no corrections: advance to iteration 1 for PR option
            iteration += 1
            html = generate_comparison_report(
                pairs=pairs,
                title=args.title,
                subtitle=args.subtitle,
                output_path=args.output,
                embed_images=True,
                server_port=port,
                iteration=iteration,
            )
            server.update_report(html)
            print(f"ITERATION_ADVANCED: No corrections on first pass — advanced to iteration {iteration}.", flush=True)
        else:
            # Corrections submitted — save them (auto_process.py was already spawned by the handler)
            with open(corrections_path, "w", encoding="utf-8") as f:
                json.dump({"iteration": iteration, "corrections": feedback}, f, indent=2)
            print(f"CORRECTIONS_SAVED: {len(feedback)} correction(s) saved.", flush=True)
            iteration += 1

            # Clear any stale flag before waiting
            if flag_path.exists():
                flag_path.unlink()

            print("WAITING_FOR_AUTO_PROCESSOR", flush=True)

            # Poll for the done flag — written by auto_process.py when finished
            import time as _time
            while not flag_path.exists():
                _time.sleep(2)
            flag_path.unlink()

            # Reload pairs and regenerate report at the new iteration
            pairs = _load_pairs(args.pairs)
            html = generate_comparison_report(
                pairs=pairs,
                title=args.title,
                subtitle=args.subtitle,
                output_path=args.output,
                embed_images=True,
                server_port=port,
                iteration=iteration,
            )
            server.update_report(html)
            print(f"REPORT_UPDATED: iteration {iteration}, {len(pairs)} pair(s).", flush=True)

    server.stop()


def _create_pr(server: CompareServer, pairs: list[dict], args: argparse.Namespace) -> None:
    """Create a PR with the before/after comparison images."""
    print("CREATING_PR...", flush=True)
    server.state = "finalizing"
    server.status_message = "Creating PR with before/after comparison images..."
    if server._server:
        server._server.state = "finalizing"
        server._server.status_message = server.status_message

    try:
        sys.path.insert(0, str(_HERE / "lib"))
        from lib import github_integration as gh

        # Build before/after image dicts from pairs
        before_images = {}
        after_images = {}
        for p in pairs:
            name = p["name"]
            left = p.get("left_path", "")
            right = p.get("right_path", "")
            if left:
                before_images[name] = left
            if right:
                if not Path(right).is_absolute():
                    right = str(Path.cwd() / right)
                after_images[name] = right

        pr_url = gh.create_comparison_pr(
            before_images=before_images,
            after_images=after_images,
            title=args.title,
        )

        # Regenerate report as finalized (read-only with PR link, no buttons)
        # and update the committed artifact
        finalized_html = generate_comparison_report(
            pairs=pairs,
            title=args.title,
            subtitle=args.subtitle,
            output_path=args.output,
            embed_images=True,
            server_port=0,
            iteration=0,
            pr_url=pr_url,
        )
        # Regenerate report as finalized (read-only with PR link, no buttons)
        # and update the committed artifact
        try:
            compare_dirs = sorted(Path("test-comparison").glob("compare-*"), reverse=True)
            if compare_dirs:
                report_dst = compare_dirs[0] / "comparison-report.html"
                report_dst.write_text(finalized_html, encoding="utf-8")
                import subprocess as _sp
                branch = _sp.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                                 capture_output=True, text=True).stdout.strip()
                gh.commit_and_push(
                    branch_name=branch,
                    message="Update comparison report with PR link\n\nCo-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>",
                    files=[str(report_dst)],
                )
        except Exception as report_exc:
            print(f"WARNING: Could not update report artifact: {report_exc}", flush=True)

        server.set_pr_url(pr_url)
        print(f"PR_CREATED: {pr_url}", flush=True)

        # Tear down resources after PR creation (unless opted out)
        if not args.no_teardown and args.resource_group:
            print(f"TEARDOWN: Deleting resource group '{args.resource_group}'...", flush=True)
            _teardown_resources(server, args)
    except Exception as exc:
        print(f"PR_ERROR: {exc}", flush=True)
        server.state = "error"
        server.status_message = f"PR creation failed: {exc}"
        if server._server:
            server._server.state = "error"
            server._server.status_message = server.status_message

    # Keep server alive so the UI can poll and show the result
    import time
    time.sleep(60)


def _teardown_resources(server: CompareServer, args: argparse.Namespace) -> None:
    """Delete the Azure resource group used for screenshot captures."""
    import subprocess
    rg = args.resource_group
    if not rg or args.no_teardown:
        print("TEARDOWN_SKIPPED: No resource group specified or --no-teardown set.", flush=True)
        server.state = "dismissed"
        if server._server:
            server._server.state = "dismissed"
        server.status_message = "No changes needed. No resources to tear down."
        if server._server:
            server._server.status_message = server.status_message
        import time
        time.sleep(30)
        return

    try:
        print(f"TEARDOWN: Deleting resource group '{rg}'...", flush=True)
        result = subprocess.run(
            ["az", "group", "delete", "--name", rg, "--yes", "--no-wait"],
            capture_output=True, text=True, timeout=60,
        )
        if result.returncode == 0:
            print(f"TEARDOWN_OK: Resource group '{rg}' deletion initiated.", flush=True)
            server.status_message = f"No changes needed. Resource group '{rg}' is being deleted."
        else:
            print(f"TEARDOWN_WARN: {result.stderr.strip()}", flush=True)
            server.status_message = f"No changes needed. Warning: resource teardown had issues."
    except Exception as exc:
        print(f"TEARDOWN_ERROR: {exc}", flush=True)
        server.status_message = f"No changes needed. Warning: could not tear down resources: {exc}"

    server.state = "dismissed"
    if server._server:
        server._server.state = "dismissed"
        server._server.status_message = server.status_message

    import time
    time.sleep(30)


if __name__ == "__main__":
    main()
