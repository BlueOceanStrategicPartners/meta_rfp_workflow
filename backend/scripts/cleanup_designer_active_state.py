"""One-off: clear stale designer 'active' UI state in DB, media uploads, LangGraph checkpoints."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import django

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local_sqlite")
django.setup()

from django.conf import settings  # noqa: E402

from apps.designer_studio.designer_graph_checkpointer import designer_checkpoint_db_path  # noqa: E402
from apps.designer_studio.models import DesignerMediaAsset, ProposalTemplate  # noqa: E402


def _clean_action_state(st: object) -> dict | None:
    if not isinstance(st, dict):
        return None
    if st.get("partial_completion") or st.get("continuation_recommended"):
        return None
    out = {k: v for k, v in st.items() if k not in ("agent_todos", "work_plan")}
    opts = out.get("clarification_options")
    if isinstance(opts, list) and opts:
        return {"clarification_options": opts[:8]}
    return None


def main() -> None:
    tpl_updated = 0
    for tpl in ProposalTemplate.objects.all():
        history = list(tpl.chat_history_json or [])
        new_history: list = []
        changed = False
        for turn in history:
            if not isinstance(turn, dict):
                new_history.append(turn)
                continue
            t = dict(turn)
            if "action_state" in t:
                cleaned = _clean_action_state(t.get("action_state"))
                if cleaned:
                    t["action_state"] = cleaned
                else:
                    t.pop("action_state", None)
                changed = True
            new_history.append(t)
        if tpl.langgraph_thread_id or tpl.langgraph_checkpoint_id:
            tpl.langgraph_thread_id = ""
            tpl.langgraph_checkpoint_id = ""
            changed = True
        if changed:
            tpl.chat_history_json = new_history
            tpl.save(
                update_fields=[
                    "chat_history_json",
                    "langgraph_thread_id",
                    "langgraph_checkpoint_id",
                    "updated_at",
                ]
            )
            tpl_updated += 1

    asset_count = DesignerMediaAsset.objects.count()
    for asset in DesignerMediaAsset.objects.iterator():
        try:
            if asset.file:
                asset.file.delete(save=False)
        except OSError:
            pass
    DesignerMediaAsset.objects.all().delete()

    media_root = Path(settings.MEDIA_ROOT)
    designer_dir = media_root / "designer_assets"
    if designer_dir.exists():
        shutil.rmtree(designer_dir)
    designer_dir.mkdir(parents=True, exist_ok=True)

    ck = designer_checkpoint_db_path()
    removed_ck: list[str] = []
    for path in (ck, Path(f"{ck}-wal"), Path(f"{ck}-shm")):
        if path.exists():
            path.unlink()
            removed_ck.append(str(path.name))

    print(f"Templates cleaned (action_state / langgraph ids): {tpl_updated}")
    print(f"DesignerMediaAsset rows removed: {asset_count}")
    print(f"Media folder reset: {designer_dir}")
    if removed_ck:
        print(f"LangGraph checkpoint files removed: {', '.join(removed_ck)}")
    else:
        print("LangGraph checkpoint files: none found")
    print("Restart the Django dev server to clear in-memory live-progress (active agent runs).")


if __name__ == "__main__":
    main()
