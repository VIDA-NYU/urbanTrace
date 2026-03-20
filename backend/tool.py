"""Copilot tool schemas and dashboard serialization helpers."""

from __future__ import annotations

import json
from typing import Any

SUGGEST_ADD_DATASET_NODE_TOOL = {
    "type": "function",
    "function": {
        "name": "suggest_add_dataset_node",
        "description": (
            "Suggest adding a dataset node to the frontend canvas by dataset id. "
            "Pass dataset_id, optionally color_by, and optionally a short reason. "
            "The frontend will let the user accept or reject the suggestion."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": "string",
                    "description": (
                        "Dataset id to add (preferred canonical id without '.geojson'). "
                        "Use dataset ids from provided UrbanTrace dataset context."
                    ),
                },
                "color_by": {
                    "type": "string",
                    "description": (
                        "Optional numeric column name to use as the default "
                        "colorBy field for the added dataset node."
                    ),
                },
                "reason": {
                    "type": "string",
                    "description": (
                        "Optional short explanation for why this dataset should be added "
                        "to the canvas right now."
                    ),
                }
            },
            "required": ["dataset_id"],
            "additionalProperties": False,
        },
    },
}

COPILOT_FRONTEND_TOOLS = [SUGGEST_ADD_DATASET_NODE_TOOL]

SUPPORTED_DATASET_SUGGESTION_TOOL_NAMES = {
    "suggest_add_dataset_node",
    "add_dataset_node",
}

ZONING_OPERATOR_RECOMMENDATION_FIELDS = (
    "dataset_name",
    "column_name",
    "classification",
    "zoningMapping",
    "zoningAggregation",
    "reasoning",
)

ZONING_OPERATOR_RECOMMENDATION_PROMPT = """
You are an expert Spatial Data Scientist and GIS Architect. Your task is to select the
optimal Zoning Mapping and Zoning Aggregation operators from the provided lists.

Step 1: Analyze the Context & Metadata
Review dataset_name and column_metadata.name together. If the column name is generic
(e.g., value, count, total, metric), you MUST rely on dataset_name to determine the meaning.
Then review num_distinct_values, distribution (mean, coverage), and sample_data.

Step 2: Classify the Data Type
- Extensive (Count/Total): high num_distinct_values, larger means, values scale with area
- Intensive (Rate/Density): decimals/floats, keywords like rate/avg/median/density
- Categorical/Ordinal (Index): low num_distinct_values (often 1-10), integer classes, index-like labels

Step 3: Geospatial Reasoning & Operator Selection
You are provided target_geometry and valid arrays: available_mapping_operators and available_aggregation_operators.
- If target is Point/MultiPoint, area-weighted mapping is invalid. Choose point-safe mapping.
- Extensive -> aggregation should preserve totals (typically Sum)
- Intensive -> aggregation should avoid absurd accumulation (typically WeightedMean/Mean/Density)
- Categorical/Ordinal -> use discrete grouping (typically Majority)

Return ONLY a valid JSON array with one object per source variable, each containing:
dataset_name, column_name, classification, zoningMapping, zoningAggregation, reasoning.
Never invent operators not present in provided arrays.
""".strip()

HOTSPOT_SYNTHESIS_FIELDS = (
    "dataset_name",
    "column_name",
    "direction",
    "reasoning",
    "weight",
)

HOTSPOT_SYNTHESIS_PROMPT = """
You are an expert urban analytics copilot. Your task is to synthesize hotspot-priority semantics.

The payload may include an optional "goal" field describing what "Priority" means in this context
(e.g. "pedestrian safety risk", "economic vulnerability", "environmental burden").
If present, use it to inform both direction and relative weight for each variable.
If absent, infer the most semantically coherent goal from the variable names and metadata.

For each source variable, infer:
- direction: "normal" (higher raw value = higher priority) OR "inverted" (lower raw value = higher priority)
- reasoning: short justification referencing the goal, dataset context, column metadata, and sample values
- weight: relative importance in [0,1]; variables more directly tied to the goal should receive higher weight

Use semantic cues from dataset_name and column_name, and validate with sample_data statistics.
Examples (goal-agnostic defaults):
- crashes/injuries/poverty/pollution -> normal
- income/coverage/infrastructure/safety score -> inverted

Return ONLY JSON array of objects with fields:
dataset_name, column_name, direction, reasoning, weight.
Do not return markdown.
""".strip()


def _normalize_dataset_id(name: str | None) -> str:
    if not isinstance(name, str):
        return ""

    dataset_id = name.strip()

    for suffix in (".geojson", ".json"):
        if dataset_id.endswith(suffix):
            dataset_id = dataset_id[: -len(suffix)]
            break

    return dataset_id


def _get_node_display_label(node: dict[str, Any]) -> str:
    data = node.get("data", {}) if isinstance(node, dict) else {}
    if not isinstance(data, dict):
        data = {}

    return (
        data.get("label")
        or data.get("name")
        or data.get("filename")
        or data.get("id")
        or node.get("id", "unknown")
    )


def _resolve_dataset_description(
    data: dict[str, Any],
    metadata: dict[str, Any],
    descriptions_by_dataset: dict[str, str],
) -> str:
    for description in (data.get("description"), metadata.get("description")):
        if isinstance(description, str) and description.strip():
            return description.strip()

    candidates = (
        data.get("id"),
        data.get("filename"),
        data.get("name"),
        metadata.get("name"),
    )
    for raw_id in candidates:
        dataset_id = _normalize_dataset_id(raw_id)
        if not dataset_id:
            continue
        description = descriptions_by_dataset.get(dataset_id)
        if description:
            return description

    return "No description available. Refer to dataset context for profile details."


def summarize_dashboard_state(
    dashboard_state: dict[str, list[dict[str, Any]]],
    descriptions_by_dataset: dict[str, str] | None = None,
) -> dict[str, Any]:
    descriptions_by_dataset = descriptions_by_dataset or {}

    nodes = dashboard_state.get("nodes", [])
    edges = dashboard_state.get("edges", [])
    node_index = {
        node.get("id"): node
        for node in nodes
        if isinstance(node, dict) and node.get("id")
    }

    dataset_nodes: list[dict[str, Any]] = []
    integration_nodes: list[dict[str, Any]] = []
    other_nodes: list[dict[str, Any]] = []

    for node in nodes:
        if not isinstance(node, dict):
            continue
        node_type = node.get("type", "unknown")
        node_id = node.get("id", "unknown")
        data = node.get("data", {})
        if not isinstance(data, dict):
            data = {}

        if node_type == "datasetNode":
            metadata = data.get("metadata", {})
            if not isinstance(metadata, dict):
                metadata = {}

            dataset_summary: dict[str, Any] = {
                "node_id": node_id,
                "dataset_id": metadata.get("name") or data.get("name"),
                "color_by": data.get("colorBy", "").strip(),
                "geometry_type": metadata.get("geometricType"),
                "columns": metadata.get("columns", []),
                "description": _resolve_dataset_description(
                    data=data,
                    metadata=metadata,
                    descriptions_by_dataset=descriptions_by_dataset,
                ),
            }

            dataset_nodes.append(dataset_summary)
        elif node_type == "integrationNode":
            integration_nodes.append(
                {
                    "node_id": node_id,
                    "label": data.get("label"),
                    "connected_source_dataset": data.get("connectedDatasetFilename"),
                    "connected_zone_dataset": data.get("connectedZoneFilename"),
                }
            )
        else:
            other_nodes.append(
                {
                    "node_id": node_id,
                    "node_type": node_type,
                    "label": _get_node_display_label(node),
                }
            )

    connections: list[dict[str, Any]] = []
    for edge in edges:
        if not isinstance(edge, dict):
            continue
        source_id = edge.get("source")
        target_id = edge.get("target")
        source_node = node_index.get(source_id, {})
        target_node = node_index.get(target_id, {})
        source_data = source_node.get("data", {}) if isinstance(source_node, dict) else {}
        target_data = target_node.get("data", {}) if isinstance(target_node, dict) else {}

        if not isinstance(source_data, dict):
            source_data = {}
        if not isinstance(target_data, dict):
            target_data = {}

        connections.append(
            {
                "edge_id": edge.get("id"),
                "source_node_id": source_id,
                "source_node_type": source_node.get("type") if isinstance(source_node, dict) else None,
                "source_label": _get_node_display_label(source_node) if source_node else source_id,
                "source_filename": source_data.get("filename"),
                "source_handle": edge.get("sourceHandle"),
                "target_node_id": target_id,
                "target_node_type": target_node.get("type") if isinstance(target_node, dict) else None,
                "target_label": _get_node_display_label(target_node) if target_node else target_id,
                "target_filename": target_data.get("filename"),
                "target_handle": edge.get("targetHandle"),
            }
        )

    return {
        "node_count": len(nodes),
        "edge_count": len(edges),
        "dataset_nodes": dataset_nodes,
        "integration_nodes": integration_nodes,
        "other_nodes": other_nodes,
        "connections": connections,
    }


def get_dashboard_snapshot_json(
    dashboard_state: dict[str, list[dict[str, Any]]],
    descriptions_by_dataset: dict[str, str] | None = None,
) -> str:
    snapshot = summarize_dashboard_state(
        dashboard_state=dashboard_state,
        descriptions_by_dataset=descriptions_by_dataset,
    )
    return json.dumps(snapshot, ensure_ascii=True)


def _build_suggestion_action(dataset_id: str, color_by: str = "") -> dict[str, Any]:
    action: dict[str, Any] = {
        "type": "add_dataset_node",
        "datasetId": dataset_id,
    }
    normalized_color_by = color_by.strip() if isinstance(color_by, str) else ""
    if normalized_color_by:
        action["colorBy"] = normalized_color_by
    return action


def _build_dataset_suggestion(
    call_id: str,
    tool_name: str,
    dataset_id: str,
    color_by: str = "",
    reason: str = "",
) -> dict[str, Any]:
    normalized_color_by = color_by.strip() if isinstance(color_by, str) else ""
    normalized_reason = reason.strip() if isinstance(reason, str) else ""
    suggestion_id = (
        f"suggestion:add_dataset_node:{dataset_id}:{normalized_color_by or 'default'}"
    )

    suggestion: dict[str, Any] = {
        "id": suggestion_id,
        "type": "add_dataset_node",
        "status": "pending",
        "title": f"Add dataset: {dataset_id}",
        "datasetId": dataset_id,
        "action": _build_suggestion_action(dataset_id, normalized_color_by),
        "sourceToolCallId": call_id,
        "sourceToolName": tool_name,
    }
    if normalized_color_by:
        suggestion["colorBy"] = normalized_color_by
    if normalized_reason:
        suggestion["reason"] = normalized_reason
    return suggestion


def build_tool_responses_from_tool_calls(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Convert model tool calls into tool response payloads (1:1 with calls).
    These are fed back to the model and can also be logged for debugging.
    """
    tool_responses: list[dict[str, Any]] = []

    for call in tool_calls:
        if not isinstance(call, dict):
            continue

        call_id = call.get("id", "")
        name = call.get("name", "")
        args = call.get("arguments", {})
        if not isinstance(args, dict):
            args = {}

        if name not in SUPPORTED_DATASET_SUGGESTION_TOOL_NAMES:
            response_payload: dict[str, Any] = {
                "status": "ignored",
                "error": f"Unsupported tool: {name}",
            }
        else:
            dataset_id = _normalize_dataset_id(args.get("dataset_id"))
            if not dataset_id:
                response_payload = {
                    "status": "error",
                    "error": "Invalid dataset_id",
                }
            else:
                color_by = args.get("color_by")
                normalized_color_by = color_by.strip() if isinstance(color_by, str) else ""
                reason = args.get("reason")
                normalized_reason = reason.strip() if isinstance(reason, str) else ""
                response_payload = {
                    "type": "suggest_add_dataset_node",
                    "status": "pending_user_decision",
                    "datasetId": dataset_id,
                    "action": _build_suggestion_action(dataset_id, normalized_color_by),
                }
                if normalized_color_by:
                    response_payload["colorBy"] = normalized_color_by
                if normalized_reason:
                    response_payload["reason"] = normalized_reason

        tool_responses.append(
            {
                "tool_call_id": call_id,
                "name": name,
                "response": response_payload,
            }
        )

    return tool_responses


def build_suggestions_from_tool_calls(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Convert model tool calls into pending frontend suggestions.
    """
    suggestions: list[dict[str, Any]] = []
    seen: set[str] = set()

    for call in tool_calls:
        if not isinstance(call, dict):
            continue
        name = call.get("name", "")
        if name not in SUPPORTED_DATASET_SUGGESTION_TOOL_NAMES:
            continue
        args = call.get("arguments", {})
        if not isinstance(args, dict):
            args = {}

        dataset_id = _normalize_dataset_id(args.get("dataset_id"))
        if not dataset_id:
            continue

        color_by = args.get("color_by")
        reason = args.get("reason")
        suggestion = _build_dataset_suggestion(
            call_id=call.get("id", ""),
            tool_name=name,
            dataset_id=dataset_id,
            color_by=color_by if isinstance(color_by, str) else "",
            reason=reason if isinstance(reason, str) else "",
        )
        dedupe_key = suggestion.get("id", "")
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        suggestions.append(suggestion)

    return suggestions


def build_frontend_actions_from_tool_calls(tool_calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Backwards-compatible helper that extracts executable actions from suggestions.
    """
    actions: list[dict[str, Any]] = []
    for suggestion in build_suggestions_from_tool_calls(tool_calls):
        action = suggestion.get("action", {})
        if isinstance(action, dict) and action.get("type"):
            actions.append(action)
    return actions
