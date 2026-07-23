"""UI shell progressive disclosure — main vs dialog panels."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_main_surface_keys_are_lean():
    from tools.director_ui_shell import main_surface_keys

    assert "shot_table" in main_surface_keys(1)
    assert "detail_cards" in main_surface_keys(1)
    assert "craft_explorer" not in main_surface_keys(1)
    assert "bundle_preview" not in main_surface_keys(1)
    assert "brief" in main_surface_keys(0)
    assert "approve_cta" in main_surface_keys(2)


def test_detail_cards_step1_and_step2():
    from tools.director_ui_shell import (
        PANEL_CRAFT,
        PANEL_EXPORT,
        detail_cards_for_step,
    )

    s1 = detail_cards_for_step(1)
    ids = {c["id"] for c in s1}
    assert PANEL_CRAFT in ids
    assert "edit_shot" in ids
    assert detail_cards_for_step(0) == []
    s2 = detail_cards_for_step(2)
    assert any(c["id"] == PANEL_EXPORT for c in s2)


def test_resolve_auto_open_prefers_screenplay_gate():
    from tools.director_ui_shell import (
        PANEL_CRAFT,
        PANEL_SCREENPLAY,
        resolve_auto_open_panel,
    )

    # While awaiting, only explicit screenplay open is honored (no force-reopen)
    assert (
        resolve_auto_open_panel(
            step=0, awaiting_screenplay=True, requested=PANEL_CRAFT
        )
        is None
    )
    assert (
        resolve_auto_open_panel(
            step=0, awaiting_screenplay=True, requested=PANEL_SCREENPLAY
        )
        == PANEL_SCREENPLAY
    )
    assert (
        resolve_auto_open_panel(
            step=1, awaiting_screenplay=False, requested=PANEL_CRAFT
        )
        == PANEL_CRAFT
    )
    assert (
        resolve_auto_open_panel(step=1, awaiting_screenplay=False, requested=None)
        is None
    )


def test_open_panel_session_helpers():
    from tools.director_ui_shell import (
        PANEL_BUNDLE,
        clear_open_panel,
        get_open_panel,
        set_open_panel,
    )

    session: dict = {}
    set_open_panel(session, PANEL_BUNDLE)
    assert get_open_panel(session) == PANEL_BUNDLE
    clear_open_panel(session)
    assert get_open_panel(session) is None
