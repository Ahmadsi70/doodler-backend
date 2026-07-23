# LangGraph Studio Orchestrator



Story uses **LangGraph** as the orchestration layer; agents remain pure functions.



## Graphs



### Brief craft — design only (`run_brief_craft_graph`)



```text

draft_screenplay → await_screenplay → [interrupt] → craft_visual → supervisor

                              ↑              → [revise → supervisor]* → complete → END

                    Command(resume={screenplay_approved: true, screenplay: {...}})

```



- **UI (Streamlit):** `park_design_for_screenplay` → human edits `screenplay_md` → `finish_design_after_screenplay`

- **Tests / CLI job:** `extras["skip_screenplay_gate"]=True` skips interrupt (one-shot craft)

- Checkpoint (job): `{job_dir}/checkpoints/brief_craft_graph.json`

- Checkpoint (LangGraph): `STORY_CHECKPOINT_DIR/studio_graph.db` (SqliteSaver; falls back to MemorySaver)



Inside `craft_visual` (P0 visual chain):

```text

approved screenplay → ScriptBreakdown → Style → Storyboard → Cine → Timing → Continuity

```



### Brief job — full export (`run_brief_studio_graph`)



```text

craft_chain → supervisor → [revise → supervisor]* → export → gate → [render] → END

```



Used by: `tools/story_pipeline.run_story_job`

- **render node** (Phase E): activated when `extras["render"]=True`. Produces MP4 (direct_render) or ready-to-run scripts (code_only).



Checkpoint: `{job_dir}/checkpoints/brief_graph.json`



### Spec export (`run_spec_export_graph` / `park` / `resume`)



```text

await_approve → [interrupt] → export → gate → [render] → END

                      ↑

              Command(resume={approved: true})

```



Used by: Director Board step 3 — `park_export_for_approval` on enter, `resume_spec_export_graph` on export.

- **render node** (Phase E): activated when `extras["render"]=True`.



Checkpoint: `{job_dir}/checkpoints/export_graph.json`



## Dependencies



```powershell

pip install langgraph langgraph-checkpoint langgraph-checkpoint-sqlite

```



If LangGraph is missing, `studio_graph` falls back to the imperative supervisor loop.



## State



`tools/studio_job_state.StudioJobState` — brief, screenplay, screenplay_approved, chain, supervisor, bundle, gate, logs, `awaiting_screenplay`, `render_requested`, `render_mode`, `render_result`.



## CLI / UI



No new flags — pipeline and Director Board call the graph automatically. UI pauses at screenplay; CLI jobs pass `skip_screenplay_gate=True`.

