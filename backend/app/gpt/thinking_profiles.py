"""Per-model thinking / reasoning profiles.

Used when enabling a model (auto-fill) and when building chat.completions kwargs.
"""

from __future__ import annotations

import os
from copy import deepcopy
from typing import Any, Dict, Optional

# mode: what we want for this model
# capability: what the provider allows
# strategy: how to encode the preference into API params

ThinkingConfig = Dict[str, Any]

DEFAULT_THINKING: ThinkingConfig = {
    "mode": "off",  # off | on | inherit
    "capability": "unknown",  # toggleable | forced_on | forced_off | unknown
    "strategy": "none",  # dashscope_enable_thinking | openai_reasoning_effort | forced_on | none
    "notes": "",
}

# Higher priority first. Patterns are lowercase substring or exact.
_RULES = [
    # Qwen max-preview: API forces thinking=True
    {
        "match": lambda n: "qwen" in n and "max-preview" in n,
        "profile": {
            "mode": "on",
            "capability": "forced_on",
            "strategy": "forced_on",
            "notes": "此模型強制開啟推理，無法關閉；建議改用 flash 以提速",
        },
    },
    {
        "match": lambda n: "qwen" in n and "flash" in n,
        "profile": {
            "mode": "off",
            "capability": "toggleable",
            "strategy": "dashscope_enable_thinking",
            "notes": "可用 enable_thinking=false 關閉推理",
        },
    },
    {
        "match": lambda n: "qwen3" in n or n.startswith("qwen"),
        "profile": {
            "mode": "off",
            "capability": "toggleable",
            "strategy": "dashscope_enable_thinking",
            "notes": "Qwen3 混合思考模型，預設嘗試關閉推理",
        },
    },
    {
        "match": lambda n: n.startswith("o1") or n.startswith("o3") or n.startswith("o4"),
        "profile": {
            "mode": "off",
            "capability": "toggleable",
            "strategy": "openai_reasoning_effort",
            "notes": "OpenAI reasoning 系列，關閉時傳 reasoning_effort=none",
        },
    },
]


def suggest_thinking_profile(model_name: str) -> ThinkingConfig:
    """Return a copy of the suggested thinking config for a model name."""
    name = (model_name or "").strip().lower()
    for rule in _RULES:
        try:
            if rule["match"](name):
                return deepcopy(rule["profile"])
        except Exception:
            continue
    return deepcopy(DEFAULT_THINKING)


def normalize_thinking(raw: Optional[Dict[str, Any]], model_name: str = "") -> ThinkingConfig:
    """Merge stored config with defaults / suggestions."""
    base = suggest_thinking_profile(model_name) if model_name else deepcopy(DEFAULT_THINKING)
    if not raw or not isinstance(raw, dict):
        return base
    thinking = raw.get("thinking") if "thinking" in raw else raw
    if not isinstance(thinking, dict):
        return base
    out = deepcopy(base)
    for key in ("mode", "capability", "strategy", "notes"):
        if key in thinking and thinking[key] is not None:
            out[key] = thinking[key]
    # legacy: reasoning_effort in config root
    if "reasoning_effort" in raw and isinstance(raw.get("reasoning_effort"), str):
        effort = raw["reasoning_effort"].lower()
        if effort in ("none", "off", "0"):
            out["mode"] = "off"
            if out["strategy"] == "none":
                out["strategy"] = "openai_reasoning_effort"
        elif effort in ("low", "medium", "high"):
            out["mode"] = "on"
            out["strategy"] = "openai_reasoning_effort"
            out["reasoning_effort"] = effort
    return out


def wrap_model_config(thinking: ThinkingConfig, existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = dict(existing or {})
    cfg["thinking"] = thinking
    return cfg


def global_thinking_enabled() -> bool:
    env = (os.getenv("LLM_ENABLE_THINKING") or "").strip().lower()
    return env in ("1", "true", "yes", "on")


def resolve_want_thinking(thinking: ThinkingConfig) -> bool:
    """Whether the request should prefer thinking ON."""
    capability = thinking.get("capability") or "unknown"
    mode = thinking.get("mode") or "off"
    if capability == "forced_on":
        return True
    if capability == "forced_off":
        return False
    if mode == "inherit":
        return global_thinking_enabled()
    if mode == "on":
        return True
    return False  # off or unknown default off


def apply_thinking_to_kwargs(kwargs: Dict[str, Any], thinking: ThinkingConfig) -> Dict[str, Any]:
    """Mutate / return chat.completions kwargs according to thinking profile."""
    strategy = thinking.get("strategy") or "none"
    want_on = resolve_want_thinking(thinking)
    capability = thinking.get("capability") or "unknown"

    if capability == "forced_on" or strategy == "forced_on":
        # Do not send enable_thinking=false — API rejects it.
        return kwargs

    if strategy == "dashscope_enable_thinking":
        extra = dict(kwargs.get("extra_body") or {})
        extra["enable_thinking"] = bool(want_on)
        kwargs["extra_body"] = extra
        return kwargs

    if strategy == "openai_reasoning_effort":
        if want_on:
            kwargs["reasoning_effort"] = thinking.get("reasoning_effort") or "medium"
        else:
            kwargs["reasoning_effort"] = "none"
        return kwargs

    # strategy none / unknown: optionally still try dashscope-style off when mode=off
    # for better defaults on hybrid models not yet catalogued
    if not want_on and capability in ("toggleable", "unknown"):
        # Conservative: only inject for names that look like qwen if strategy is none
        pass
    return kwargs
