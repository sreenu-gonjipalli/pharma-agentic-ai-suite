#!/usr/bin/env python3
"""OpenRouter client wrapper for DevGuard (CLAUDE.md Section 5).

Loads the config/models.yaml route table, calls the named route via the OpenAI-compatible
OpenRouter API, and captures token counts + latency for every call (the Phase 8 Trace +
observability work will consume this same result shape). Rule 5 (CLAUDE.md Section 2): model
IDs come only from models.yaml -- never hardcoded here, never a ":free" suffix on this path,
and prompt/response content is never logged or printed -- only route name, model, token
counts, latency, and cost are ever reported.
"""
import argparse
import os
import time
from pathlib import Path

import yaml
from openai import APIConnectionError, APIStatusError, NotFoundError, OpenAI, RateLimitError
from pydantic import BaseModel

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config" / "models.yaml"


class RouteCallResult(BaseModel):
    route: str
    model: str
    latency_seconds: float
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float


def load_config() -> dict:
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


def _client(config: dict) -> OpenAI:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set -- copy .env.example to .env and fill it in.")
    return OpenAI(base_url=config["base_url"], api_key=key)


def call_route(route_name: str, messages: list, config: dict = None):
    """Calls the model pinned for `route_name` in models.yaml. Returns
    (message_content, RouteCallResult). Never logs `messages` -- Rule 5, prompt logging
    disabled."""
    config = config or load_config()
    routes = config["routes"]
    if route_name not in routes:
        raise ValueError(f"Unknown route '{route_name}'. Known routes: {sorted(routes)}")
    route = routes[route_name]
    model = route["model"]
    if model.endswith(":free"):
        raise RuntimeError(
            f"Route '{route_name}' resolves to a ':free' model ({model}) -- Rule 5 forbids "
            "':free' models on the demo path."
        )

    client = _client(config)
    start = time.monotonic()
    resp = client.chat.completions.create(model=model, messages=messages)
    elapsed = time.monotonic() - start

    usage = resp.usage
    prompt_tokens = usage.prompt_tokens if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0
    total_tokens = usage.total_tokens if usage else 0
    cost = (
        prompt_tokens / 1_000_000 * route["price_per_1m_in"]
        + completion_tokens / 1_000_000 * route["price_per_1m_out"]
    )

    result = RouteCallResult(
        route=route_name,
        model=model,
        latency_seconds=round(elapsed, 3),
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        cost_usd=round(cost, 8),
    )
    return resp.choices[0].message.content, result


def call_route_with_retry(route_name: str, messages: list, config: dict = None, max_retries: int = 2):
    """Retries `call_route` a few times on transient failures -- a malformed/empty response
    body, a dropped connection, or a rate limit -- before giving up. Never retries a
    `NotFoundError` (this account's OpenRouter guardrail policy blocks most routes with a 404;
    that is a permanent per-route block, not a transient fault, so retrying only burns calls)."""
    config = config or load_config()
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            content, result = call_route(route_name, messages, config)
            if not content or not content.strip():
                raise ValueError("empty/malformed completion content")
            return content, result
        except NotFoundError:
            raise
        except (APIConnectionError, RateLimitError, APIStatusError, ValueError) as exc:
            last_exc = exc
            if attempt < max_retries:
                time.sleep(0.5 * (attempt + 1))
    raise last_exc


def main():
    parser = argparse.ArgumentParser(description="DevGuard OpenRouter client (Phase 0 scaffold).")
    parser.add_argument("--ping", action="store_true",
                         help="Send a minimal completion on a route and report tokens/latency.")
    parser.add_argument("--route", default="triage_guardrail",
                         help="Route name from config/models.yaml (default: triage_guardrail, the cheapest route).")
    args = parser.parse_args()

    if not args.ping:
        parser.print_help()
        return

    config = load_config()
    _, result = call_route(
        args.route, [{"role": "user", "content": "Reply with the single word: pong"}], config
    )
    print("Route call succeeded (prompt/response content intentionally not printed -- Rule 5):")
    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
