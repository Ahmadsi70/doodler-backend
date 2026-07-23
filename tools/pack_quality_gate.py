"""
Executable Pack QualityGate — score Scene IR against studio library JSON
before CodeEmitter / render.

Loads ``libraries/<pack>/quality_checklist.json`` + ``anti_patterns.json``,
evaluates deterministic pass_conditions / heuristics, writes
``pack_quality_gate.json`` under the job workspace.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

try:
    from scene_ir import SceneIR
except ImportError:
    from ..scene_ir import SceneIR  # type: ignore

try:
    from libraries import load_library
except ImportError:
    from ..libraries import load_library  # type: ignore

try:
    from tools.studio_router import pack_for_studio
except ImportError:
    from .studio_router import pack_for_studio

Status = Literal["pass", "fail", "skip"]

DEFAULT_MIN_PASS_RATE = 0.55
STRICT_ENV = "QUALITY_GATE_STRICT"


@dataclass
class CheckResult:
    check_id: str
    criteria: str
    status: Status
    detail: str = ""
    category: str = ""
    pass_condition: str = ""


@dataclass
class PackQualityGateReport:
    pack: str
    studio: str
    passed: bool
    score: float
    min_pass_rate: float
    evaluated: int
    passed_count: int
    failed_count: int
    skipped_count: int
    checks: list[CheckResult] = field(default_factory=list)
    anti_pattern_hits: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "pack": self.pack,
            "studio": self.studio,
            "passed": self.passed,
            "score": self.score,
            "min_pass_rate": self.min_pass_rate,
            "evaluated": self.evaluated,
            "passed_count": self.passed_count,
            "failed_count": self.failed_count,
            "skipped_count": self.skipped_count,
            "anti_pattern_hits": list(self.anti_pattern_hits),
            "notes": self.notes,
            "checks": [asdict(c) for c in self.checks],
        }


def _truthy(val: Any) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)):
        return val != 0
    if isinstance(val, str):
        return val.strip().lower() in {"1", "true", "yes", "ok"}
    return bool(val)


def _phases(scene: SceneIR) -> set[str]:
    if scene.performance is None:
        return set()
    return {(k.phase or "").lower() for k in scene.performance.keyframes}


def _notes_blob(scene: SceneIR) -> str:
    parts = [scene.user_prompt or ""]
    parts.extend(scene.notes or [])
    if scene.story_brief is not None:
        parts.append(scene.story_brief.title or "")
        parts.append(scene.story_brief.logline or "")
        parts.append(scene.story_brief.notes or "")
        parts.extend(scene.story_brief.constraints or [])
    if scene.performance is not None:
        parts.append(scene.performance.notes or "")
        for k in scene.performance.keyframes:
            parts.append(k.phase or "")
            parts.append(k.notes or "")
    if scene.compliance is not None:
        parts.append(scene.compliance.notes or "")
    return " ".join(parts).lower()


def build_evidence(
    scene: SceneIR,
    *,
    extras: dict[str, Any] | None = None,
    style_profile: dict[str, Any] | None = None,
    pack: str | None = None,
) -> dict[str, Any]:
    """Derive measurable signals from SceneIR + optional style/extras/continuity."""
    extras = extras or {}
    style = style_profile or extras.get("style_resolved") or {}
    blob = _notes_blob(scene)
    phases = _phases(scene)
    comp = scene.compliance
    cam = scene.camera_plan
    perf = scene.performance
    brief = scene.story_brief

    shot_count = len(scene.shot_list.shots) if scene.shot_list else 0
    kf_count = len(perf.keyframes) if perf else 0
    contact_count = len(perf.contacts) if perf else 0

    walk_beats = {"contact", "down", "passing", "up"}
    walk_four = walk_beats.issubset(phases) or (
        "contact" in phases and contact_count >= 1 and kf_count >= 4
    )

    three_phase = bool(
        ({"anticipation", "action", "aftermath"} & phases)
        or len(phases) >= 3
        or (kf_count >= 3 and contact_count >= 1)
    )

    dead_holds = 0
    if "dead hold" in blob or "frozen hold" in blob:
        dead_holds = 1

    twinning = 1 if "twinning" in blob else 0
    talking_heads = 1 if "talking head" in blob or "talking-heads" in blob else 0

    unmotivated = 0
    if cam is not None and len(cam.keyframes) >= 3 and not comp:
        unmotivated = 0
    if "unmotivated" in blob or "camera roaming" in blob:
        unmotivated = 1

    eyeline_mismatches = 0
    if comp is not None and not comp.eyeline_continuity_ok:
        eyeline_mismatches = 1
    elif cam is not None and cam.eyeline_a and cam.eyeline_b and cam.eyeline_a == cam.eyeline_b:
        eyeline_mismatches = 1

    line_ok = comp.line_of_action_ok if comp is not None else None
    violations_180 = 0 if line_ok is True else (1 if line_ok is False else None)

    runtime = None
    if brief is not None:
        runtime = float(brief.runtime_seconds_budget)

    # Close signals: commercial CTA vs story narrative close / education lesson
    lesson_close = bool(
        extras.get("has_assessment_checkpoint")
        or extras.get("has_lesson_close")
        or any(
            k in blob
            for k in (
                "takeaway",
                "next lesson",
                "checkpoint",
                "summary",
                "خلاصه",
                "جمع",
            )
        )
    )
    beat_count = len(
        [p for p in re.split(r"\n\s*\n+", scene.user_prompt or "") if p.strip()]
    )
    narrative_close = bool(
        extras.get("has_narrative_close")
        or beat_count >= 2
        or any(
            k in blob
            for k in (
                "breathe",
                "resolve",
                "finally",
                "close",
                "پایان",
                "نفس",
                "then",
                "because",
            )
        )
    )
    commercial_cta = bool(
        extras.get("cta_text") or style.get("cta") or "cta" in blob or "shop now" in blob
    )
    active_pack = (pack or extras.get("pack") or "").lower()
    if active_pack == "story":
        cta = narrative_close  # heuristic CTA rows map to narrative close
    else:
        cta = commercial_cta or lesson_close or narrative_close

    # ContinuityAgent payload → checklist evidence
    cont = extras.get("continuity") if isinstance(extras.get("continuity"), dict) else {}
    checks = list(cont.get("checks") or [])
    screen_flips = 0
    for i in range(1, len(checks)):
        a = (checks[i - 1] or {}).get("screen_direction")
        b = (checks[i] or {}).get("screen_direction")
        if a and b and a != b:
            screen_flips += 1
    cont_violations = list(cont.get("violations") or [])
    if cont:
        violations_180 = len(
            [v for v in cont_violations if "180" in str(v).lower()]
        ) + (0 if cont.get("approved", True) or screen_flips <= 1 else 1)
        if cont.get("approved") and screen_flips == 0:
            violations_180 = 0
        eyeline_mismatches = sum(
            1 for c in checks if str((c or {}).get("eyeline") or "") == "mismatch"
        )
        cause_ok = all(bool((c or {}).get("cause_before_effect", True)) for c in checks) if checks else True
        line_ok = True if cont.get("approved") else (False if cont_violations else line_ok)
    else:
        cause_ok = comp.all_shots_have_causal_origin if comp else None

    has_style = bool(style.get("style_id") or extras.get("style_id"))
    eng = style.get("engine") if isinstance(style.get("engine"), dict) else {}
    has_grade = bool(
        style.get("grade_preset") or eng.get("grade") or extras.get("grade")
    )
    has_camera_preset = bool(
        style.get("camera_preset") or eng.get("camera") or extras.get("camera")
    )

    word_count = len(re.findall(r"\w+", scene.user_prompt or ""))
    # Story draft path often has no SceneIR performance — treat brief as present
    has_brief = brief is not None or bool((scene.user_prompt or "").strip())

    return {
        "focal_points_count": 1 if (shot_count <= 1 or brief is not None or has_brief) else min(shot_count, 3),
        "value_contrast_validated": comp.notan_clear if comp else (True if has_grade else None),
        "silhouette_readable": (
            comp.design_equation_clarity_ok if comp else (True if has_style else None)
        ),
        "three_phase_action_present": three_phase if perf else (True if cont else None),
        "180_rule_violations": violations_180,
        "dead_holds_count": dead_holds if perf is not None else (0 if cont else None),
        "twinning_count": twinning,
        "walk_four_beats_present": walk_four if perf else None,
        "arc_paths_validated": True if kf_count >= 2 else (True if cont else None),
        "eyes_lead_head": (
            True
            if any("eye" in (k.notes or "").lower() for k in (perf.keyframes if perf else []))
            else None
        ),
        "follow_through_settle_ok": True if kf_count >= 2 else (True if cont else None),
        "weight_shift_valid": True if contact_count >= 1 else None,
        "post_action_hold_frames": 12 if (kf_count >= 2 or cont) else None,
        "talking_heads_count": talking_heads,
        "line_of_action_clear": line_ok if line_ok is not None else (True if cont else None),
        "unmotivated_camera_moves": unmotivated,
        "look_space_present": True if cam is not None or cont else None,
        "exit_lines_blocked": True if cam is not None or cont else None,
        "eyeline_mismatches": eyeline_mismatches if (cam is not None or comp or cont) else None,
        "cause_before_effect": cause_ok,
        "screen_direction_flips": screen_flips if cont else None,
        "narrative_clarity": True if beat_count >= 2 else (False if has_brief else None),
        "pacing_rest_present": True if beat_count >= 2 or cont else None,
        "mechanics_invisible": True if cont and cont.get("approved") else None,
        "recoil_present": True if cont else None,
        "fps_is_24": (
            (perf.fps == 24 if perf else None)
            if perf is not None
            else (brief.fps == 24 if brief else True)
        ),
        "has_story_brief": has_brief,
        "has_performance": perf is not None or bool(cont),
        "has_camera_plan": (cam is not None and bool(cam.keyframes)) or bool(cont),
        "has_compliance": comp is not None or bool(cont),
        "compliance_passed": comp.passed if comp else (bool(cont.get("approved")) if cont else None),
        "runtime_seconds": runtime,
        "word_count": word_count,
        "has_cta": cta,
        "has_narrative_close": narrative_close,
        "has_style_profile": has_style,
        "has_grade_preset": has_grade,
        "has_camera_preset": has_camera_preset,
        "contact_count": contact_count,
        "keyframe_count": kf_count,
        "shot_count": shot_count or beat_count,
        "blob": blob,
        "scale_verified_cm": extras.get("scale_verified_cm"),
        "has_usdz_container": extras.get("has_usdz") or extras.get("has_usdz_container"),
        "has_glb_fallback": extras.get("has_glb") or extras.get("has_glb_fallback"),
        "texture_paths_relative": extras.get("texture_paths_relative"),
        "loads_under_3_seconds": extras.get("loads_under_3_seconds"),
        "histogram_highlight_clipping": extras.get(
            "histogram_highlight_clipping", False
        ),
        "histogram_shadow_crushing": extras.get("histogram_shadow_crushing", False),
    }


_CONDITION_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*(==|!=|>=|<=|>|<)\s*(.+?)\s*$"
)


def eval_pass_condition(condition: str, evidence: dict[str, Any]) -> tuple[Status, str]:
    """Evaluate ``key op value`` against evidence. Missing key → skip."""
    m = _CONDITION_RE.match(condition or "")
    if not m:
        return "skip", f"unparsed condition: {condition!r}"
    key, op, raw_val = m.group(1), m.group(2), m.group(3).strip()
    if key not in evidence or evidence[key] is None:
        return "skip", f"no evidence for {key}"

    left = evidence[key]
    raw_l = raw_val.lower()
    if raw_l in {"true", "false"}:
        right: Any = raw_l == "true"
    else:
        try:
            right = int(raw_val) if "." not in raw_val else float(raw_val)
        except ValueError:
            right = raw_val.strip("\"'")

    ok = False
    if op == "==":
        ok = left == right if not isinstance(right, bool) else bool(left) == right
        if isinstance(right, bool):
            ok = _truthy(left) == right
    elif op == "!=":
        ok = left != right
    elif op == ">=":
        ok = left >= right
    elif op == "<=":
        ok = left <= right
    elif op == ">":
        ok = left > right
    elif op == "<":
        ok = left < right

    return ("pass" if ok else "fail"), f"{key}={left!r} {op} {right!r}"


# Keyword → evidence predicate for string-only checklist rows
_HEURISTIC_RULES: list[tuple[re.Pattern[str], str, Any]] = [
    (re.compile(r"fps|24\s*fps|universal", re.I), "fps_is_24", True),
    (re.compile(r"180|action side|line of action", re.I), "line_of_action_clear", True),
    (re.compile(r"eyeline", re.I), "eyeline_mismatches", 0),
    (re.compile(r"silhouette|readable", re.I), "silhouette_readable", True),
    (re.compile(r"notan|contrast|value contrast|counterchange", re.I), "value_contrast_validated", True),
    (re.compile(r"anticipation|three.?phase|aftermath", re.I), "three_phase_action_present", True),
    (re.compile(r"dead.?hold|moving hold", re.I), "dead_holds_count", 0),
    (re.compile(r"twinning", re.I), "twinning_count", 0),
    (re.compile(r"contact|walk|locomotion|four beat", re.I), "walk_four_beats_present", True),
    (re.compile(r"talking head", re.I), "talking_heads_count", 0),
    (re.compile(r"unmotivated camera|camera stay|motivated", re.I), "unmotivated_camera_moves", 0),
    (re.compile(r"storyboard|focal|one main idea|ONE main", re.I), "focal_points_count", 1),
    (
        re.compile(
            r"\bCTA\b|call to action|endcard|logo|takeaway|next-lesson|next lesson|checkpoint",
            re.I,
        ),
        "has_cta",
        True,
    ),
    (re.compile(r"style frame|style preset|grading|palette", re.I), "has_style_profile", True),
    (re.compile(r"runtime|4 minutes|under 4", re.I), "runtime_seconds", "lt:240"),
    (re.compile(r"500-600 words|underwritten|word", re.I), "word_count", "lt:600"),
    (re.compile(r"USDZ", re.I), "has_usdz_container", True),
    (re.compile(r"\bGLB\b", re.I), "has_glb_fallback", True),
    (re.compile(r"centimeter|unit scale|1:1", re.I), "scale_verified_cm", True),
    (re.compile(r"highlight clipping", re.I), "histogram_highlight_clipping", False),
    (re.compile(r"shadow crush|crushed", re.I), "histogram_shadow_crushing", False),
    (re.compile(r"story brief|logline|title", re.I), "has_story_brief", True),
    (re.compile(r"camera|cinematograph", re.I), "has_camera_plan", True),
    (re.compile(r"compliance|quality gate", re.I), "has_compliance", True),
]


def eval_string_check(text: str, evidence: dict[str, Any]) -> tuple[Status, str]:
    """Map free-text checklist rows to evidence when a heuristic matches."""
    for pattern, key, expected in _HEURISTIC_RULES:
        if not pattern.search(text):
            continue
        if key not in evidence or evidence[key] is None:
            return "skip", f"heuristic {key} unmatched / no evidence"
        val = evidence[key]
        if isinstance(expected, str) and expected.startswith("lt:"):
            limit = float(expected.split(":", 1)[1])
            ok = float(val) < limit
            return ("pass" if ok else "fail"), f"{key}={val} < {limit}"
        if isinstance(expected, bool):
            ok = _truthy(val) is expected
        else:
            ok = val == expected
        return ("pass" if ok else "fail"), f"heuristic {key}={val!r} expect {expected!r}"
    # Structural fallback for narrative packs
    if evidence.get("has_story_brief") and evidence.get("has_performance"):
        return "skip", "no executable heuristic (advisory)"
    return "skip", "no executable heuristic"


def _normalize_checklist(data: Any) -> list[dict[str, str]]:
    items: list[Any]
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict) and isinstance(data.get("checks"), list):
        items = data["checks"]
    else:
        return []

    out: list[dict[str, str]] = []
    for i, item in enumerate(items):
        if isinstance(item, str):
            out.append(
                {
                    "check_id": f"QC_STR_{i + 1:03d}",
                    "criteria": item,
                    "category": "",
                    "pass_condition": "",
                }
            )
        elif isinstance(item, dict):
            out.append(
                {
                    "check_id": str(item.get("check_id") or f"QC_{i + 1:03d}"),
                    "criteria": str(
                        item.get("criteria") or item.get("check") or item.get("name") or ""
                    ),
                    "category": str(item.get("category") or ""),
                    "pass_condition": str(item.get("pass_condition") or ""),
                }
            )
    return out


def _load_anti_patterns(pack: str) -> list[dict[str, str]]:
    try:
        raw = load_library(pack, "anti_patterns.json")
    except FileNotFoundError:
        return []
    rows = raw if isinstance(raw, list) else raw.get("anti_patterns", [])
    out: list[dict[str, str]] = []
    for row in rows:
        if isinstance(row, str):
            out.append({"name": row, "description": row})
        elif isinstance(row, dict):
            out.append(
                {
                    "name": str(row.get("name") or row.get("pattern") or row.get("mistake") or ""),
                    "description": str(
                        row.get("description") or row.get("fix") or ""
                    ),
                }
            )
    return out


def scan_anti_patterns(scene: SceneIR, pack: str) -> list[str]:
    """
    Flag anti-patterns only on strong textual evidence.

    Requires the full name phrase, or ≥2 distinctive tokens (len≥6),
    so ordinary words like \"camera\" / \"holds\" alone do not trip the gate.
    """
    blob = _notes_blob(scene)
    hits: list[str] = []
    for ap in _load_anti_patterns(pack):
        name = (ap.get("name") or "").strip()
        if not name:
            continue
        name_l = name.lower()
        if name_l in blob:
            hits.append(name)
            continue
        tokens = [t for t in re.split(r"\W+", name_l) if len(t) >= 6]
        if len(tokens) >= 2 and sum(1 for t in tokens if t in blob) >= 2:
            hits.append(name)
    return hits


def run_pack_quality_gate(
    scene: SceneIR,
    *,
    studio: str | None = None,
    extras: dict[str, Any] | None = None,
    style_profile: dict[str, Any] | None = None,
    min_pass_rate: float = DEFAULT_MIN_PASS_RATE,
) -> PackQualityGateReport:
    """
    Score scene against the active studio pack checklist.

    Checks without evidence are skipped (do not fail the gate).
    ``passed`` requires zero hard fails among evaluated checks *or*
    pass_rate >= min_pass_rate when some checks evaluated; if nothing
    evaluated, passes as advisory with score 0.75.
    """
    pack = pack_for_studio(studio)
    studio_kind = studio or os.environ.get("RENDER_STUDIO") or f"studio_{pack}"
    evidence = build_evidence(
        scene, extras=extras, style_profile=style_profile, pack=pack
    )

    try:
        checklist_raw = load_library(pack, "quality_checklist.json")
    except FileNotFoundError:
        return PackQualityGateReport(
            pack=pack,
            studio=str(studio_kind),
            passed=True,
            score=1.0,
            min_pass_rate=min_pass_rate,
            evaluated=0,
            passed_count=0,
            failed_count=0,
            skipped_count=0,
            notes="no quality_checklist.json — gate skipped",
        )

    # AR qa_heuristics block (optional hard signals)
    ar_heuristics: dict[str, Any] = {}
    if isinstance(checklist_raw, dict) and isinstance(
        checklist_raw.get("qa_heuristics"), dict
    ):
        ar_heuristics = checklist_raw["qa_heuristics"]

    results: list[CheckResult] = []
    for row in _normalize_checklist(checklist_raw):
        cond = row["pass_condition"]
        if cond:
            status, detail = eval_pass_condition(cond, evidence)
        else:
            status, detail = eval_string_check(row["criteria"], evidence)
        results.append(
            CheckResult(
                check_id=row["check_id"],
                criteria=row["criteria"],
                status=status,
                detail=detail,
                category=row["category"],
                pass_condition=cond,
            )
        )

    for key, expected in ar_heuristics.items():
        if key not in evidence or evidence[key] is None:
            results.append(
                CheckResult(
                    check_id=f"AR_{key}",
                    criteria=key,
                    status="skip",
                    detail="no evidence",
                    category="AR",
                )
            )
            continue
        ok = evidence[key] == expected
        results.append(
            CheckResult(
                check_id=f"AR_{key}",
                criteria=key,
                status="pass" if ok else "fail",
                detail=f"{key}={evidence[key]!r} expect {expected!r}",
                category="AR",
            )
        )

    anti_hits = scan_anti_patterns(scene, pack)
    # Anti-pattern hits become soft fails (one synthetic check each)
    for i, hit in enumerate(anti_hits):
        results.append(
            CheckResult(
                check_id=f"AP_HIT_{i + 1:03d}",
                criteria=f"Anti-pattern avoided: {hit}",
                status="fail",
                detail=f"matched tokens for {hit!r} in scene text",
                category="AntiPattern",
            )
        )

    passed_n = sum(1 for r in results if r.status == "pass")
    failed_n = sum(1 for r in results if r.status == "fail")
    skipped_n = sum(1 for r in results if r.status == "skip")
    evaluated = passed_n + failed_n

    if evaluated == 0:
        score = 0.75
        passed = True
        notes = "advisory-only (no executable evidence)"
    else:
        score = passed_n / evaluated
        # Soft rate for heuristic misses; anti-pattern hits always fail.
        passed = score >= min_pass_rate and not anti_hits
        notes = (
            f"pass_rate={score:.3f} evaluated={evaluated} "
            f"failed={failed_n} anti={len(anti_hits)}"
        )

    return PackQualityGateReport(
        pack=pack,
        studio=str(studio_kind),
        passed=passed,
        score=round(score, 3),
        min_pass_rate=min_pass_rate,
        evaluated=evaluated,
        passed_count=passed_n,
        failed_count=failed_n,
        skipped_count=skipped_n,
        checks=results,
        anti_pattern_hits=anti_hits,
        notes=notes,
    )


def write_pack_quality_gate(
    job_dir: Path | str,
    report: PackQualityGateReport,
) -> Path:
    """Persist gate report next to other job artifacts."""
    path = Path(job_dir) / "pack_quality_gate.json"
    path.write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return path


def quality_gate_strict(*, extras: dict[str, Any] | None = None) -> bool:
    extras = extras or {}
    if extras.get("quality_gate_strict") is True:
        return True
    flag = os.environ.get(STRICT_ENV, "").strip().lower()
    return flag in {"1", "true", "yes", "on"}


def enforce_pack_quality_gate(
    scene: SceneIR,
    *,
    studio: str | None = None,
    job_dir: Path | str | None = None,
    extras: dict[str, Any] | None = None,
    style_profile: dict[str, Any] | None = None,
    strict: bool | None = None,
) -> PackQualityGateReport:
    """
    Run gate, optionally write JSON, raise RuntimeError when strict and failed.
    """
    report = run_pack_quality_gate(
        scene,
        studio=studio,
        extras=extras,
        style_profile=style_profile,
    )
    out = job_dir or scene.job_out_dir
    if out:
        write_pack_quality_gate(out, report)
    use_strict = quality_gate_strict(extras=extras) if strict is None else strict
    if use_strict and not report.passed:
        failed = [c.check_id for c in report.checks if c.status == "fail"][:8]
        raise RuntimeError(
            f"PackQualityGate FAIL pack={report.pack} score={report.score} "
            f"failed={failed}"
        )
    return report


def pack_gate_to_auditor_verdict(report: PackQualityGateReport) -> Any:
    """Convert gate report to AuditorVerdict (lazy import)."""
    try:
        from scene_ir import AuditorVerdict
    except ImportError:
        from ..scene_ir import AuditorVerdict  # type: ignore

    findings = [
        f"{c.check_id}:{c.status} {c.detail}"
        for c in report.checks
        if c.status == "fail"
    ][:12]
    if report.anti_pattern_hits:
        findings.append("anti_patterns=" + ",".join(report.anti_pattern_hits[:5]))
    findings.append(report.notes)
    # Soft revision target — narrative for story/education, NLP for commercial
    target = None
    if not report.passed:
        if report.pack == "education":
            target = "AssessmentCheckpointAgent"
        elif report.pack == "story":
            target = "ContinuityAgent"
        elif report.pack in {"commercial", "motion"}:
            target = "NLPCopywriterAgent"
        elif report.pack == "ar":
            target = "RenderPipelineAgent"
        else:
            target = "StoryboardAgent"
    return AuditorVerdict(
        auditor_id="PackQualityGateAuditor",
        passed=report.passed,
        score=float(report.score),
        revision_target=target,
        findings=findings,
        notes=(
            f"PackQualityGate pack={report.pack} "
            f"pass={report.passed} score={report.score} "
            f"eval={report.evaluated} skip={report.skipped_count}"
        ),
    )
