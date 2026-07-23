# GitHub remote + CI (Story)

`C:\Users\badri\Story` is a **standalone** git repo (`git init` done).  
Wire a remote and let Actions run `.github/workflows/ci.yml`.

## One-time setup (Windows)

```powershell
cd C:\Users\badri\Story

# Install GitHub CLI if missing
winget install --id GitHub.cli -e

gh auth login
gh repo create Story --private --source=. --remote=origin --push
```

If `gh` is unavailable, create an empty repo on GitHub then:

```powershell
git remote add origin https://github.com/<USER>/Story.git
git branch -M master
git push -u origin master
```

## Local CI (same gates as Actions)

```powershell
cd C:\Users\badri\Story
python -c "from tools.ci_local import ci_local_plan; import json; print(json.dumps(ci_local_plan(), indent=2))"
$env:ANIMATION_DETERMINISTIC_SLIDES=1; $env:STORY_USE_LLM=0
python -m pytest tests -q --tb=short
python scripts/smoke_render.py
```

## Branches

CI triggers on `push` to `main` / `master` and on pull requests.
