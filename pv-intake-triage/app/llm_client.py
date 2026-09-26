#!/usr/bin/env python3
"""LLM access for the standalone pipeline (intake/triage/narrative reasoning steps).

Two OpenAI-API-compatible providers, tried in order: OpenRouter first (OPENROUTER_API_KEY,
already present in this environment), then Groq (GROQ_API_KEY) if OpenRouter is unavailable
or errors. Coding (MedDRA lookup) and duplicate search stay deterministic/local -- see
pipeline.py -- so only intake extraction, triage rationale, and narrative drafting go through
an LLM at all. No provider here is ever given a case-approval or external-transmission
capability (Business Rule 3, CLAUDE.md Section 3) -- this module only ever returns text/JSON
to the caller.
"""
import json
import os
import re

from openai import OpenAI

OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "anthropic/claude-sonnet-5")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "openai/gpt-oss-20b")


def _openrouter_client():
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return None
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key), OPENROUTER_MODEL, "openrouter"


def _groq_client():
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        return None
    return OpenAI(base_url="https://api.groq.com/openai/v1", api_key=key), GROQ_MODEL, "groq"


def available_providers():
    names = []
    if os.environ.get("OPENROUTER_API_KEY"):
        names.append("openrouter")
    if os.environ.get("GROQ_API_KEY"):
        names.append("groq")
    return names


def _strip_markdown_fence(text: str) -> str:
    """Some models (e.g. Claude via OpenRouter) wrap JSON in a ```json ... ``` fence even when
    response_format=json_object is requested -- OpenRouter doesn't enforce that mode uniformly
    across providers. Strip the fence before parsing, but only that -- never touch the JSON
    content itself."""
    match = re.search(r"```(?:json)?\s*(.*?)\s*```", text, re.DOTALL)
    return match.group(1) if match else text


def chat_json(system_prompt: str, user_prompt: str, temperature: float = 0.0) -> tuple:
    """Call the first working provider, asking for a strict JSON object reply.
    Returns (parsed_dict, provider_name_used). Raises RuntimeError if every provider fails."""
    attempts = [c for c in (_openrouter_client(), _groq_client()) if c is not None]
    if not attempts:
        raise RuntimeError(
            "No LLM provider configured -- set OPENROUTER_API_KEY or GROQ_API_KEY in the "
            "environment before running the pipeline."
        )

    errors = []
    for client, model, name in attempts:
        try:
            resp = client.chat.completions.create(
                model=model,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
            )
            raw = resp.choices[0].message.content
            return json.loads(_strip_markdown_fence(raw)), name
        except Exception as e:  # noqa: BLE001 -- deliberately broad: fall through to next provider
            errors.append(f"{name}: {e}")

    raise RuntimeError("Every configured LLM provider failed:\n" + "\n".join(errors))
