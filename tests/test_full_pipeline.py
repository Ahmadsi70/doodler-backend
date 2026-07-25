"""
Full end-to-end pipeline test.
Runs all agents sequentially, catches errors, reports results.
"""
from __future__ import annotations

import io
import json
import sys
import time
import traceback
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from chat.chat_session import ChatSession
from chat.agent_bus import AgentBus
from agents.chat_agent_wrapper import register_all_agents

BRIEF = "یک انیمیشن ۵ ثانیه‌ای درباره قهرمانی که وارد غار تاریک می‌شود، گنجی پیدا می‌کند و جشن می‌گیرد"


def test_agent(agent_name: str, bus: AgentBus, session: ChatSession) -> dict:
    """Run a single agent and return {ok, error, events, output}."""
    import asyncio

    result = {"name": agent_name, "ok": False, "error": None, "events": [], "outputs": {}}
    try:
        events = asyncio.run(bus.run_agent(agent_name, session.brief, session))
        result["events"] = events
        # Check for errors
        for ev in events:
            if ev.get("type") == "error":
                result["error"] = ev.get("content", "Unknown error")
                return result
            if ev.get("type") == "agent_error":
                result["error"] = ev.get("error", "Unknown error")
                return result
        result["ok"] = True
    except Exception as e:
        result["error"] = f"{type(e).__name__}: {e}"
        result["traceback"] = traceback.format_exc()
    return result


def main():
    print("=" * 60)
    print("  Story Studio — Full Pipeline Test")
    print("=" * 60)
    print(f"\nBrief: {BRIEF}\n")

    bus = AgentBus()
    register_all_agents(bus)
    session = ChatSession.create_welcome_session()
    session.brief = BRIEF

    agents = bus.list_agents()
    auto_agents = [a for a in agents if a["mode"] == "auto"]
    manual_agents = [a for a in agents if a["mode"] == "manual"]

    # ── Phase 1: Run AUTO agents in dependency order ──────────────
    print("\n── Phase 1: AUTO pipeline ──")
    results = {}
    all_ok = True

    for a in auto_agents:
        name = a["name"]
        deps_ok = all(results.get(d, {}).get("ok", False) for d in a["dependencies"] if d in auto_agents)
        if not deps_ok:
            missing = [d for d in a["dependencies"] if d in auto_agents and not results.get(d, {}).get("ok")]
            results[name] = {"ok": False, "error": f"Dependencies not met: {missing}"}
            print(f"  ❌ {name} — SKIPPED (deps failed: {missing})")
            continue

        print(f"  ▶ Running {name}...", end=" ")
        start = time.time()
        result = test_agent(name, bus, session)
        elapsed = time.time() - start
        results[name] = result

        if result["ok"]:
            print(f"✅ ({elapsed:.1f}s)")
            # Show summary of output
            last_msg = session.get_last_agent_message(name)
            if last_msg:
                content_preview = last_msg.content[:100].replace("\n", " ")
                print(f"     Output: {content_preview}...")
                if last_msg.attachments:
                    for att in last_msg.attachments:
                        print(f"     Attachment: {att.type} / {att.label} ({len(att.content)} chars)")
        else:
            print(f"❌ ({elapsed:.1f}s)")
            print(f"     ERROR: {result['error']}")
            if result.get("traceback"):
                tb = result["traceback"]
                print(f"     Traceback (last 5 lines):")
                for line in tb.strip().split("\n")[-5:]:
                    print(f"       {line}")
            all_ok = False

    # ── Phase 2: Check session metadata ──────────────────────────
    print("\n── Session Metadata ──")
    meta_keys = list(session.metadata.keys())
    print(f"  Keys: {meta_keys}")
    if "frame_pipeline_state" in session.metadata:
        fps = session.metadata["frame_pipeline_state"]
        print(f"  FramePipeline state: present")
        print(f"    performance_chart: {fps.get('performance_chart') is not None}")
        print(f"    contact_lock: {fps.get('contact_lock') is not None}")
        print(f"    camera_curves: {fps.get('camera_curves') is not None}")
        print(f"    acting_lead: {fps.get('acting_lead') is not None}")
        print(f"    phoneme_sync: {fps.get('phoneme_sync') is not None}")
        print(f"    audio_timeline: {fps.get('audio_timeline') is not None}")
        print(f"    frame_gate: {fps.get('frame_gate') is not None}")

    # ── Phase 3: Run MANUAL agents (RenderAgent) ─────────────────
    print("\n── Phase 2: MANUAL agents ──")
    for a in manual_agents:
        name = a["name"]
        if name == "RubberDuck":
            continue  # Skip RubberDuck — it's interactive
        print(f"  ▶ Running {name}...", end=" ")
        start = time.time()
        result = test_agent(name, bus, session)
        elapsed = time.time() - start
        results[name] = result

        if result["ok"]:
            print(f"✅ ({elapsed:.1f}s)")
            last_msg = session.get_last_agent_message(name)
            if last_msg:
                content_preview = last_msg.content[:120].replace("\n", " ")
                print(f"     Output: {content_preview}...")
                if last_msg.attachments:
                    for att in last_msg.attachments:
                        print(f"     Attachment: {att.type} / {att.label} ({len(att.content)} chars)")
        else:
            print(f"❌ ({elapsed:.1f}s)")
            print(f"     ERROR: {result['error']}")
            all_ok = False

    # ── Phase 4: Verify story_props ──────────────────────────────
    print("\n── Final Verification ──")
    if "story_props" in session.metadata:
        sp = session.metadata["story_props"]
        print(f"  story_props: {sp.get('title')}")
        print(f"  Shots: {len(sp.get('shots') or [])}")
        for key in ["performanceChart", "contactLock", "cameraCurves", "actingLead", "phonemeSync", "foleyTimeline", "frameGate"]:
            print(f"    {key}: {sp.get(key) is not None}")
    else:
        print("  ❌ story_props NOT in session metadata")


    # ── Summary ───────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  RESULTS SUMMARY")
    print("=" * 60)
    total = len(results)
    passed = sum(1 for r in results.values() if r["ok"])
    failed = total - passed
    print(f"  Total: {total} | ✅ Passed: {passed} | ❌ Failed: {failed}")
    for name, r in results.items():
        status = "✅" if r["ok"] else "❌"
        err = f" — {r['error']}" if r.get("error") else ""
        print(f"  {status} {name}{err}")

    if failed > 0:
        print("\n⚠ Some agents failed. Check errors above.")
        return False
    else:
        print("\n🎉 All agents passed!")
        return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
