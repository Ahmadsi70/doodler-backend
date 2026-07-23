"""
Import Kenney Impact Sounds (CC0) into libraries/audio with stable cue_ids.

Source: https://kenney.nl/assets/impact-sounds (CC0)
Mirror used: github.com/Boyquotes/kenney-impact-sounds-for-godot
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = ROOT / "_audio_src"
FILES = ROOT / "libraries" / "audio" / "files"
CATALOG = ROOT / "libraries" / "audio" / "catalog.json"
CUES = ROOT / "libraries" / "audio" / "cues.json"
ATTR = ROOT / "libraries" / "audio" / "ATTRIBUTION.md"
TARGET_N = 100


def _ffmpeg() -> str:
    found = shutil.which("ffmpeg")
    if not found:
        raise RuntimeError("ffmpeg required to convert .ogg → .wav")
    return found


def _cue_id_from_stem(stem: str) -> str:
    """
    Map Kenney stems to project cue_ids.

    Examples:
      footstep_carpet_000 → foley_footstep_carpet_00
      impactSoft_heavy_001 → foley_hit_soft_heavy_01
      impactWood_medium_004 → foley_hit_wood_medium_04
      land_000 → foley_land_00
    """
    s = stem.strip()
    m = re.match(r"^(.*?)_(\d+)$", s)
    if m:
        base, num = m.group(1), int(m.group(2))
    else:
        base, num = s, 0
    base_l = base.replace("-", "_")

    if base_l.lower().startswith("footstep_"):
        material = base_l.split("_", 1)[1].lower()
        return f"foley_footstep_{material}_{num:02d}"
    if base_l.lower().startswith("land"):
        return f"foley_land_{num:02d}"
    if base_l.startswith("impactSoft"):
        rest = base_l[len("impactSoft") :].lstrip("_").lower() or "soft"
        return f"foley_hit_soft_{rest}_{num:02d}"
    if base_l.startswith("impactWood"):
        rest = base_l[len("impactWood") :].lstrip("_").lower() or "wood"
        return f"foley_hit_wood_{rest}_{num:02d}"
    if base_l.startswith("impactPlate") or base_l.startswith("impactMetal"):
        rest = re.sub(r"^impact(Plate|Metal)_?", "", base_l, flags=re.I).lower() or "metal"
        return f"foley_hit_metal_{rest}_{num:02d}"
    if base_l.startswith("impactPunch"):
        rest = base_l[len("impactPunch") :].lstrip("_").lower() or "punch"
        return f"foley_hit_punch_{rest}_{num:02d}"
    if base_l.startswith("impactGeneric") or base_l.startswith("impact"):
        rest = re.sub(r"^impact(Generic)?_?", "", base_l, flags=re.I).lower() or "generic"
        return f"foley_hit_generic_{rest}_{num:02d}"
    # fallback
    safe = re.sub(r"[^a-z0-9_]+", "_", base_l.lower()).strip("_")
    return f"foley_{safe}_{num:02d}"


def _tags_for_cue(cue_id: str) -> list[str]:
    tags = ["kenney", "cc0", "impact"]
    if "footstep" in cue_id:
        tags += ["footstep", "foley", "walk"]
    if "land" in cue_id:
        tags += ["land", "foley", "impact"]
    if "hit_soft" in cue_id:
        tags += ["hit", "soft", "foley", "reaction"]
    if "hit_wood" in cue_id:
        tags += ["hit", "wood", "foley"]
    if "hit_metal" in cue_id:
        tags += ["hit", "metal", "foley", "tense"]
    if "hit_punch" in cue_id:
        tags += ["hit", "punch", "conflict", "reaction"]
    if "hit_generic" in cue_id:
        tags += ["hit", "generic", "foley"]
    for mat in ("carpet", "concrete", "grass", "wood", "snow", "metal", "dirt"):
        if mat in cue_id:
            tags.append(mat)
    for w in ("heavy", "medium", "light"):
        if w in cue_id:
            tags.append(w)
    return sorted(set(tags))


def _beats_for_cue(cue_id: str) -> list[str]:
    if "footstep" in cue_id or "land" in cue_id:
        return ["entrance", "exit"]
    if "hit_soft" in cue_id:
        return ["reaction", "quiet_hold"]
    if "hit_punch" in cue_id or "hit_metal" in cue_id:
        return ["reaction", "conflict"]
    if "hit_wood" in cue_id or "hit_generic" in cue_id:
        return ["conflict", "reveal", "reaction"]
    return ["decision"]


def _role_for_cue(cue_id: str) -> str:
    if "footstep" in cue_id or "land" in cue_id or "hit_" in cue_id:
        return "oneshot"
    return "oneshot"


def main() -> None:
    oggs = sorted(SRC_ROOT.rglob("*.ogg"))
    if len(oggs) < TARGET_N:
        raise SystemExit(f"Need ≥{TARGET_N} oggs, found {len(oggs)}")
    FILES.mkdir(parents=True, exist_ok=True)
    # clear previous imported wavs that look like foley_* from this importer
    for old in FILES.glob("foley_*.wav"):
        old.unlink()

    ff = _ffmpeg()
    cues: dict[str, dict] = {}
    selected = oggs[:TARGET_N]
    for src in selected:
        cue_id = _cue_id_from_stem(src.stem)
        # ensure uniqueness
        base_id = cue_id
        n = 1
        while cue_id in cues:
            cue_id = f"{base_id}_{n}"
            n += 1
        dest = FILES / f"{cue_id}.wav"
        cmd = [
            ff,
            "-y",
            "-i",
            str(src),
            "-ac",
            "1",
            "-ar",
            "22050",
            str(dest),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0 or not dest.is_file():
            raise RuntimeError(f"ffmpeg failed for {src.name}: {proc.stderr[-500:]}")
        cues[cue_id] = {
            "file": f"files/{cue_id}.wav",
            "source_file": src.name,
            "role": _role_for_cue(cue_id),
            "tags": _tags_for_cue(cue_id),
            "beats": _beats_for_cue(cue_id),
            "gain_db": -10 if "footstep" in cue_id else -8,
            "loop": False,
            "license": "CC0-1.0",
            "attribution": "Kenney.nl Impact Sounds",
        }

    # Keep legacy semantic aliases for pipeline compatibility
    aliases = {
        "foley_footstep": next((k for k in cues if k.startswith("foley_footstep_")), None),
        "foley_hit_soft": next((k for k in cues if "hit_soft" in k), None),
        "stinger_reveal": next((k for k in cues if "hit_metal" in k or "hit_generic" in k), None),
    }
    for alias, target in aliases.items():
        if not target:
            continue
        row = dict(cues[target])
        row["alias_of"] = target
        row["file"] = cues[target]["file"]
        cues[alias] = row

    # Preserve procedural beds if present
    for bed in ("ambience_soft", "ambience_tense", "silence_hold"):
        bed_path = FILES / f"{bed}.wav"
        if bed_path.is_file():
            cues.setdefault(
                bed,
                {
                    "file": f"files/{bed}.wav",
                    "role": "bed" if bed.startswith("ambience") else "oneshot",
                    "tags": ["procedural", "bed"] if "ambience" in bed else ["silence"],
                    "beats": (
                        ["entrance", "quiet_hold", "decision"]
                        if bed == "ambience_soft"
                        else (
                            ["reaction", "conflict"]
                            if bed == "ambience_tense"
                            else ["quiet_hold"]
                        )
                    ),
                    "gain_db": -18 if "ambience" in bed else -60,
                    "loop": "ambience" in bed,
                    "license": "generated",
                },
            )

    catalog = {
        "schema": "audio_catalog#v1",
        "source": {
            "name": "Kenney Impact Sounds",
            "url": "https://kenney.nl/assets/impact-sounds",
            "license": "CC0-1.0",
            "count_imported": TARGET_N,
            "mirror": "https://github.com/Boyquotes/kenney-impact-sounds-for-godot",
        },
        "cues": cues,
    }
    CATALOG.write_text(json.dumps(catalog, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    CUES.write_text(
        json.dumps(
            {
                "schema": "audio_drama_cues#v1",
                "cues": {
                    k: {
                        "file": v["file"],
                        "gain_db": v.get("gain_db", -10),
                        "loop": bool(v.get("loop")),
                        "beats": list(v.get("beats") or []),
                        "role": v.get("role"),
                        "tags": list(v.get("tags") or []),
                    }
                    for k, v in cues.items()
                },
                "notes": "Primary library: Kenney Impact Sounds CC0 (100). Beds may be procedural.",
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    ATTR.write_text(
        """# Audio attribution

## Kenney Impact Sounds

- Source: https://kenney.nl/assets/impact-sounds
- License: [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)
- Author: Kenney (www.kenney.nl)
- Files imported: 100 (converted OGG→WAV)
- Attribution optional under CC0; credited here in gratitude.

Mirror used for automated fetch:
https://github.com/Boyquotes/kenney-impact-sounds-for-godot (CC0-1.0)
""",
        encoding="utf-8",
    )
    print(f"imported={TARGET_N} catalog={CATALOG} files={FILES}")


if __name__ == "__main__":
    main()
