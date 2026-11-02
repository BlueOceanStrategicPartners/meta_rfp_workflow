import json
import os
import sys

import django
import httpx

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local_sqlite")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
django.setup()

from django.conf import settings  # noqa: E402

from apps.rfp_debate.muse_structured_schemas import structured_response_format
from apps.designer_studio.design_agent_tool_loop import TOOL_LOOP_SYSTEM  # noqa: E402
from apps.designer_studio.template_workspace import TemplateWorkspace  # noqa: E402
from apps.designer_studio.tool_loop_context import build_tool_loop_user_intro  # noqa: E402

ws = TemplateWorkspace("", "", "")
user_block = build_tool_loop_user_intro(
    message="Create interactive template",
    history=[],
    context_prefix="",
    workspace=ws,
)
messages = [
    {"role": "system", "content": TOOL_LOOP_SYSTEM},
    {"role": "user", "content": user_block[:32000]},
]
payload = {
    "model": settings.META_MODEL_SPARK,
    "messages": messages,
    "response_format": structured_response_format(
        name="DesignerToolLoopStep",
        schema=__import__(
            "apps.rfp_debate.muse_structured_schemas",
            fromlist=["DESIGNER_TOOL_LOOP_STEP"],
        ).DESIGNER_TOOL_LOOP_STEP,
    ),
}
base = settings.META_MODEL_API_BASE.rstrip("/")
r = httpx.post(
    f"{base}/chat/completions",
    json=payload,
    headers={"Authorization": f"Bearer {settings.META_MODEL_API_KEY}"},
    timeout=120.0,
)
print("status", r.status_code)
data = r.json()
choice = data["choices"][0]
msg = choice["message"]
content = msg.get("content") or ""
print("finish_reason", choice.get("finish_reason"))
print("content_len", len(content))
print("content_head", repr(content[:600]))
if content.strip():
    try:
        from apps.rfp_debate.meta_client import parse_model_json_content

        parsed = parse_model_json_content(content)
        print("parsed_kind", parsed.get("kind"))
        print("tools", len(parsed.get("tools") or []))
    except (json.JSONDecodeError, ValueError) as exc:
        print("parse_error", exc)
