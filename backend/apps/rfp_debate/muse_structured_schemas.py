"""JSON Schema payloads for Meta Model API structured output (response_format json_schema).

See https://dev.meta.ai/docs/structured-output
"""
from __future__ import annotations

from typing import Any

# Tool-loop agent turn: finish or multi-tool batch (arguments are tool-specific).
DESIGNER_TOOL_LOOP_STEP: dict[str, Any] = {
    "type": "object",
    "properties": {
        "kind": {
            "type": "string",
            "enum": ["finish", "tools", "tool"],
            "description": "finish when done; tools for one or more tool calls",
        },
        "tool": {"type": "string", "description": "Legacy single-tool name when kind is tool"},
        "arguments": {
            "type": "object",
            "description": "Arguments for a single tool when kind is tool",
        },
        "tools": {
            "type": "array",
            "description": "Batch of tools when kind is tools",
            "items": {
                "type": "object",
                "properties": {
                    "tool": {"type": "string"},
                    "arguments": {"type": "object"},
                },
                "required": ["tool", "arguments"],
            },
        },
        "assistant_message": {"type": "string"},
        "clarification_options": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["kind"],
}

DESIGNER_EXECUTION_PLAN: dict[str, Any] = {
    "type": "object",
    "properties": {
        "steps": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                },
                "required": ["id", "label"],
            },
        },
        "summary": {"type": "string"},
    },
    "required": ["steps"],
}

DESIGNER_WORK_PLAN_LABELS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "labels": {
            "type": "object",
            "additionalProperties": {"type": "string"},
        },
    },
    "required": ["labels"],
}

DESIGNER_CHAT_TEMPLATE: dict[str, Any] = {
    "type": "object",
    "properties": {
        "assistant_message": {"type": "string"},
        "html_markup": {"type": "string"},
        "css_stylesheet": {"type": "string"},
        "js_script": {"type": "string"},
        "clarification_options": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["assistant_message", "html_markup", "css_stylesheet", "js_script"],
}

DESIGNER_VALIDATION_RESULT: dict[str, Any] = {
    "type": "object",
    "properties": {
        "valid": {"type": "boolean"},
        "issues": {"type": "array", "items": {"type": "string"}},
        "summary": {"type": "string"},
    },
    "required": ["valid", "issues"],
}

DESIGNER_RULE_CONFLICT: dict[str, Any] = {
    "type": "object",
    "properties": {
        "has_conflict": {"type": "boolean"},
        "explanation": {"type": "string"},
        "conflicting_rule_ids": {"type": "array", "items": {"type": "string"}},
        "suggested_rule": {"type": "string"},
    },
    "required": ["has_conflict"],
}

DESIGNER_ASSET_META: dict[str, Any] = {
    "type": "object",
    "properties": {
        "description": {"type": "string"},
        "suggested_placement": {"type": "string"},
        "dominant_mood": {"type": "string"},
        "embed_hint": {"type": "string"},
    },
    "required": ["description"],
}

VOICE_REPLY: dict[str, Any] = {
    "type": "object",
    "properties": {
        "reply": {"type": "string"},
        "message": {"type": "string"},
    },
}

RFP_CRITIQUE_RESULT: dict[str, Any] = {
    "type": "object",
    "properties": {
        "discrepancy_flags": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "field_path": {"type": "string"},
                    "severity": {"type": "string"},
                    "message": {"type": "string"},
                    "expected": {"type": "string"},
                    "actual": {"type": "string"},
                },
                "required": ["field_path", "severity", "message"],
            },
        },
        "consensus_score": {"type": "number"},
    },
    "required": ["discrepancy_flags", "consensus_score"],
}

# Open object — field-level shape enforced by Pydantic parse_extraction after decode.
RFP_EXTRACTION_PAYLOAD: dict[str, Any] = {
    "type": "object",
    "description": "RFPExtractionPayload with cited fields",
}

# fixture_kind -> (schema_name, schema dict) for Chat Completions structured output
FIXTURE_STRUCTURED_SCHEMAS: dict[str, tuple[str, dict[str, Any]]] = {
    "designer_tool_loop": ("DesignerToolLoopStep", DESIGNER_TOOL_LOOP_STEP),
    "designer_tool_loop_repair": ("DesignerToolLoopStep", DESIGNER_TOOL_LOOP_STEP),
    "designer_execution_plan": ("DesignerExecutionPlan", DESIGNER_EXECUTION_PLAN),
    "designer_work_plan": ("DesignerWorkPlanLabels", DESIGNER_WORK_PLAN_LABELS),
    "designer_chat": ("DesignerChatTemplate", DESIGNER_CHAT_TEMPLATE),
    "designer_validate": ("DesignerValidationResult", DESIGNER_VALIDATION_RESULT),
    "designer_save_validate": ("DesignerValidationResult", DESIGNER_VALIDATION_RESULT),
    "designer_rule_validate": ("DesignerRuleConflict", DESIGNER_RULE_CONFLICT),
    "designer_asset_meta": ("DesignerAssetMeta", DESIGNER_ASSET_META),
    "voice_reply": ("VoiceAssistantReply", VOICE_REPLY),
    "rfp_extraction": ("RfpExtractionPayload", RFP_EXTRACTION_PAYLOAD),
    "rfp_critique": ("RfpCritiqueResult", RFP_CRITIQUE_RESULT),
}


def structured_response_format(
    *,
    name: str,
    schema: dict[str, Any],
    strict: bool = False,
) -> dict[str, Any]:
    """Build Meta Chat Completions response_format for json_schema structured output."""
    return {
        "type": "json_schema",
        "json_schema": {
            "name": name,
            "schema": schema,
            "strict": strict,
        },
    }


def structured_response_format_for_fixture(
    fixture_kind: str | None,
) -> dict[str, Any] | None:
    if not fixture_kind:
        return None
    mapped = FIXTURE_STRUCTURED_SCHEMAS.get(fixture_kind)
    if not mapped:
        return None
    schema_name, schema = mapped
    return structured_response_format(name=schema_name, schema=schema)
