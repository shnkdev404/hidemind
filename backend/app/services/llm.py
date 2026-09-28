"""Groq gateway: JSON output, validation, retries. Used for the amnesia baseline and PDF extraction."""

import json
import logging
import re

import groq
from pydantic import BaseModel, ValidationError
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ..config import get_settings

log = logging.getLogger("munshi.llm")
_client: groq.AsyncGroq | None = None

_RETRYABLE = (groq.RateLimitError, groq.APIConnectionError, groq.InternalServerError, groq.APITimeoutError)


class LLMUnavailable(RuntimeError):
    pass


def _get_client() -> groq.AsyncGroq:
    global _client
    s = get_settings()
    if not s.llm_enabled:
        raise LLMUnavailable("GROQ_API_KEY is not configured")
    if _client is None:
        _client = groq.AsyncGroq(api_key=s.groq_api_key, timeout=60, max_retries=0)
    return _client


@retry(retry=retry_if_exception_type(_RETRYABLE), wait=wait_exponential(min=2, max=30),
       stop=stop_after_attempt(5), reraise=True)
async def _complete(messages: list[dict], temperature: float) -> str:
    resp = await _get_client().chat.completions.create(
        model=get_settings().agent_model,
        messages=messages,
        temperature=temperature,
        response_format={"type": "json_object"},
    )
    return resp.choices[0].message.content or ""


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise
        return json.loads(match.group(0))


async def chat_json(system: str, user: str, model: type[BaseModel], temperature: float = 0.1) -> BaseModel:
    """Ask for JSON, validate against `model`, retry once with the validation error fed back."""
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    last_err: Exception | None = None
    for _ in range(2):
        text = await _complete(messages, temperature)
        try:
            return model.model_validate(_extract_json(text))
        except (json.JSONDecodeError, ValidationError) as e:
            last_err = e
            log.warning("LLM returned invalid JSON, retrying: %s", e)
            messages += [{"role": "assistant", "content": text},
                         {"role": "user", "content": f"That was invalid: {e}. Return only valid JSON."}]
    raise ValueError(f"LLM output failed validation: {last_err}")
