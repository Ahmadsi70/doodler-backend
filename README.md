# Story — Kids Story Studio

North star (ordered, non-interfering lanes — see `libraries/product_layers.py`):

| Lane | Product | Entry |
|------|---------|--------|
| **A** | Kids Storybook Film — watercolor stills + live color pen + Ken Burns | `scripts/produce_storybook.py`, `produce_scene_pack.py` |
| **B** | Kids Edu Micro-Lessons — A visuals + short English narration | `scripts/produce_edu_lesson.py` |
| **C** | Full Cartoon Studio — future lip-sync / character motion (stub) | `scripts/produce_cartoon_studio.py` |

**A pipeline:** Topic / scene pack → directed page stills → live pen → Ken Burns → `final.mp4`  
**B** adds TTS mux only; **C** must not replace A compose or B narration.

No cutouts, SAM, dual-plate Telea, or ink_reveal puppet layers in Lane A.

## Setup

```powershell
cd C:\Users\badri\Story
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# set GEMINI_API_KEY or GOOGLE_API_KEY in .env for --live
```

## Produce

```powershell
# Mock (no API):
python scripts/produce_storybook.py --mock --title "Lantern Fox" --target-sec 36 --out out/storybook --topic "A fox finds a lantern. Fireflies gather. Mist rises."

# Live stills + Gemini critique:
python scripts/produce_storybook.py --live --critique --critique-fa --title "Lantern Fox" --target-sec 36 --out out/storybook_live --topic "..."
```

Critique only:

```powershell
python scripts/critique_video.py --video out/storybook/final.mp4 --live --fa
```

## Pen-draw (cartoon stroke reveal)

Headless (automated, OpenCV — good for pipeline):

```powershell
python scripts/pen_draw_still.py --still out/storybook_fox_v4/pages/page_00.png --out out/pen_draw_page00.mp4 --duration-sec 4
```

Inkplainer-OS UI (richer browser tool — manual Generate/Export):

```powershell
python scripts/open_inkplainer.py --still out/storybook_fox_v4/pages/page_00.png
```

## Tests

```powershell
python -m pytest tests -q
```

## Layout

| Path | Role |
|------|------|
| `agents/storybook_page_agent.py` | Topic → page plan |
| `agents/narrative_beat_agent.py` | Clause split + timing |
| `libraries/storybook_pipeline.py` | Stills + Ken Burns compose |
| `libraries/gemini_client.py` | Live still generation |
| `libraries/video_critique.py` | Gemini QC |
| `scripts/produce_storybook.py` | CLI |
