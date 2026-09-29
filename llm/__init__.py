"""
LLM query interpretation layer.

Converts natural-language questions into validated StructuredQuery objects
via the Groq API. This package has exactly one responsibility:
NL → Groq → validated StructuredQuery. It never generates SQL, accesses
databases, or invents facts about wells.
"""

from .groq_interpreter import GroqInterpreter, InterpretationError, InterpretationResult

__all__ = [
    "GroqInterpreter",
    "InterpretationError",
    "InterpretationResult",
]
