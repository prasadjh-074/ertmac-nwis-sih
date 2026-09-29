"""
Groq → StructuredQuery interpreter.

Takes a natural-language question, sends it to Groq's API with a system
prompt that describes the StructuredQuery contract, parses the JSON
response, and validates it against query.StructuredQuery. Returns a
validated StructuredQuery on success or raises InterpretationError.

This module has exactly one responsibility: NL → validated StructuredQuery.
It never generates SQL, accesses databases, or invents facts.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from groq import Groq

from query.schema import StructuredQuery
from query.validator import QueryValidationError, validate_query

from .prompts import SYSTEM_PROMPT

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "openai/gpt-oss-20b"
DEFAULT_TEMPERATURE = 0.0
DEFAULT_MAX_TOKENS = 1024
MAX_RETRIES = 2


class InterpretationError(Exception):
    """Raised when the interpreter cannot produce a valid StructuredQuery."""

    def __init__(self, message: str, raw_response: Optional[str] = None, validation_errors: Optional[list] = None):
        self.raw_response = raw_response
        self.validation_errors = validation_errors or []
        super().__init__(message)


@dataclass
class InterpretationResult:
    """Wraps a successful interpretation with observability metadata."""

    query: StructuredQuery
    model: str
    latency_ms: float
    prompt_tokens: int
    completion_tokens: int
    raw_json: Dict[str, Any]
    retries: int = 0


@dataclass
class GroqInterpreter:
    """Stateless interpreter: NL question → Groq API → validated StructuredQuery."""

    model: str = field(default_factory=lambda: os.getenv("GROQ_MODEL", DEFAULT_MODEL))
    temperature: float = DEFAULT_TEMPERATURE
    max_tokens: int = DEFAULT_MAX_TOKENS
    _client: Optional[Groq] = field(default=None, repr=False)

    def __post_init__(self):
        if self._client is None:
            load_dotenv()
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise InterpretationError(
                    "GROQ_API_KEY not set. Set it in your environment or a .env file."
                )
            self._client = Groq(api_key=api_key)

    def interpret(self, question: str) -> InterpretationResult:
        """Convert a natural-language question to a validated StructuredQuery.

        Sends the question to Groq with json_mode, parses the response,
        validates against the StructuredQuery contract, and retries once
        with the validation error appended if the first attempt fails
        validation.
        """
        if not question or not question.strip():
            raise InterpretationError("Question must be a non-empty string.")

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question.strip()},
        ]

        last_error = None
        retries = 0

        for attempt in range(1 + MAX_RETRIES):
            t0 = time.monotonic()

            try:
                response = self._client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    response_format={"type": "json_object"},
                )
            except Exception as exc:
                raise InterpretationError(f"Groq API call failed: {exc}") from exc

            latency_ms = (time.monotonic() - t0) * 1000
            raw_text = response.choices[0].message.content

            logger.info(
                "Groq response (attempt %d, %.0fms): %s",
                attempt + 1, latency_ms, raw_text[:200],
            )

            try:
                parsed = json.loads(raw_text)
            except json.JSONDecodeError as exc:
                last_error = InterpretationError(
                    f"Groq returned invalid JSON: {exc}",
                    raw_response=raw_text,
                )
                if attempt < MAX_RETRIES:
                    retries += 1
                    messages.append({"role": "assistant", "content": raw_text})
                    messages.append({
                        "role": "user",
                        "content": f"That was not valid JSON. Return ONLY a JSON object. Error: {exc}",
                    })
                    continue
                raise last_error

            try:
                validated = validate_query(parsed)
            except QueryValidationError as exc:
                last_error = InterpretationError(
                    f"Groq output failed schema validation: {exc}",
                    raw_response=raw_text,
                    validation_errors=exc.errors,
                )
                if attempt < MAX_RETRIES:
                    retries += 1
                    messages.append({"role": "assistant", "content": raw_text})
                    messages.append({
                        "role": "user",
                        "content": (
                            f"That JSON failed validation. Errors: {exc.errors}. "
                            "Fix the JSON and return ONLY the corrected JSON object."
                        ),
                    })
                    continue
                raise last_error

            usage = response.usage
            return InterpretationResult(
                query=validated,
                model=self.model,
                latency_ms=latency_ms,
                prompt_tokens=usage.prompt_tokens if usage else 0,
                completion_tokens=usage.completion_tokens if usage else 0,
                raw_json=parsed,
                retries=retries,
            )

        raise last_error
