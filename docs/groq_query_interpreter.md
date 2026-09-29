# Groq → StructuredQuery Interpreter

Status: implemented and tested. This is the NL interpretation layer only —
it does not execute queries, access databases, or build any frontend/backend.

## What it does

Takes a natural-language question about wells and geology, sends it to
Groq's LLM API, and validates the JSON response against the existing
`query.StructuredQuery` contract. Returns a validated `StructuredQuery`
on success.

```
User question (string)
    → Groq API (system prompt + user message, json_mode)
    → JSON response
    → Pydantic validation (query.validate_query)
    → InterpretationResult (validated StructuredQuery + metadata)
```

## Single responsibility

The interpreter has exactly one job: **NL → validated StructuredQuery**.
It never:
- Generates SQL
- Accesses any database
- Invents well names or geological facts
- Answers the user's question directly
- Builds any UI or API endpoint

## Model selection

Default: `llama-3.3-70b-versatile` (Groq's Llama 3.3 70B, ~280 tok/s).
Configurable via the `GROQ_MODEL` environment variable.

The model is called with `response_format={"type": "json_object"}` to
guarantee JSON output, and `temperature=0.0` for deterministic results.

## Configuration

Environment variables (load from `.env` for development):

| Variable | Required | Default | Description |
|---|---|---|---|
| `GROQ_API_KEY` | yes | — | Groq API key (never hard-coded) |
| `GROQ_MODEL` | no | `llama-3.3-70b-versatile` | Groq model ID |

A `.env.example` file is provided with placeholders.

## Usage

```python
from llm import GroqInterpreter

interp = GroqInterpreter()  # reads GROQ_API_KEY from env/.env

result = interp.interpret("Find wells similar to 15/9-F-1")
# result.query  → validated StructuredQuery
# result.model  → "llama-3.3-70b-versatile"
# result.latency_ms → 342.1
# result.prompt_tokens → 1250
# result.completion_tokens → 45
# result.raw_json → {"intent": "similar_wells", ...}
# result.retries → 0
```

## Error handling

- **No API key**: `InterpretationError("GROQ_API_KEY not set...")`
- **Empty question**: `InterpretationError("Question must be a non-empty string.")`
- **API failure**: `InterpretationError("Groq API call failed: ...")`
- **Invalid JSON from Groq**: retries up to 2 times with the error appended,
  then raises `InterpretationError` with `raw_response` attached
- **Schema validation failure**: retries up to 2 times with validation errors
  appended, then raises `InterpretationError` with `validation_errors` list

## Retry strategy

If Groq returns invalid JSON or JSON that fails StructuredQuery validation,
the interpreter appends the error to the conversation and retries (up to 2
retries = 3 total attempts). The retry message includes the specific
validation errors so the LLM can self-correct.

## System prompt design

The system prompt (`llm/prompts.py`) teaches the LLM:
1. The 6 intents and when to use each
2. All fields with types and constraints
3. Per-intent required/optional/forbidden field rules
4. Dataset identification heuristics (15/9-F-* → VOLVE)
5. 6 worked examples
6. Critical rules: no SQL, no invented facts, no direct answers

## Testing

### Mocked tests (no API key needed)

```bash
pytest tests/test_groq_interpreter.py -v -m "not live"
```

16 tests covering:
- All 6 intents (tests A–F)
- Empty/whitespace questions
- Invalid JSON from Groq (with retry verification)
- Schema validation failures (with retry verification)
- SQL injection in user question
- Extra fields from Groq (extra="forbid" enforcement)
- Missing API key
- API exceptions
- Observability metadata
- Retry logic (first attempt fails, second succeeds)

### Live tests (require GROQ_API_KEY)

```bash
GROQ_API_KEY=your-key pytest tests/test_groq_interpreter.py -v -m live
```

6 live tests that hit the real Groq API and validate the response.

### Full suite

```bash
pytest tests/ -v -m "not live"   # 90 tests total (16 retrieval + 58 query + 16 interpreter)
```

## Package layout

```
llm/
├── __init__.py          — public exports (GroqInterpreter, InterpretationError, InterpretationResult)
├── groq_interpreter.py  — interpreter class with retry logic
└── prompts.py           — system prompt (StructuredQuery contract for the LLM)
```

## Security

- `GROQ_API_KEY` is loaded from environment only — never hard-coded,
  printed, or committed
- `.env` is in `.gitignore`
- The system prompt forbids SQL generation
- Even if Groq returns extra fields or SQL-shaped content, Pydantic's
  `extra="forbid"` and the well_id pattern constraint reject it
- SQL injection in user questions produces a valid StructuredQuery
  (the LLM structures the question, it doesn't execute it)

## What's explicitly deferred

- A resolver that turns a validated StructuredQuery into actual
  `retrieval.*` calls or SQL against `core.*`/`subsurface.*`
- LangGraph or any agentic orchestration
- Frontend/backend of any kind
- Conversation memory or multi-turn context
