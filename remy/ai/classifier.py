"""
Message complexity classifier.
Decides whether to route to a simple/cheap model or a complex/capable one.

Fast-path heuristics run first (no network).
Ambiguous messages fall back to a single Haiku call for 2-token classification.
"""

import logging
import re
from typing import Literal

logger = logging.getLogger(__name__)

# Keywords that strongly signal a complex, agentic or tool-use task
_COMPLEX_PATTERNS = re.compile(
    r"""
    (?xi)
    \bwrite\b.*\b(?:script|function|class|file|test|code)\b
    | \bcreate\b.*\b(?:project|module|app|api|bot|function|script|class)\b
    | \brefactor\b | \bdebug\b | \bfix\s+(?:the|this|a)\b
    | \bbuild\b | \bimplement\b | \bgenerate\s+(?:code|a)\b
    | \bcommit\b | \bgit\b | \bdeploy\b
    | \.py\b | \.ts\b | \.js\b | \.sh\b   # file extensions
    | ```                                   # code fences
    | (?:step\s+\d|first.*then.*finally)    # multi-step instructions
    | /board                                # board command
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Messages that are clearly simple greetings or short questions
_SIMPLE_PATTERNS = re.compile(
    r"^(?:hi|hello|hey|thanks?|thank\s+you|ok|okay|cool|great|sure|yes|no|nope|yep)\b",
    re.IGNORECASE,
)

ClassificationResult = Literal[
    "routine",         # Short interactive messages, greetings
    "summarization",   # Email summaries, doc summaries
    "reasoning",       # Planning, multi-step tasks, board analysis
    "safety",          # File writes, financial actions (if any)
    "coding",          # Scripting, code generation
    "persona",         # Roleplay
]


class MessageClassifier:
    """Classify messages into categories for optimal model routing."""

    def __init__(self, claude_client=None) -> None:
        # claude_client injected to avoid circular imports; used only for ambiguous cases
        self._claude = claude_client

    async def classify(self, text: str) -> ClassificationResult:
        """Return a task category for the given message text."""
        stripped = text.strip()

        # Fast-path: obvious routine cases
        if len(stripped) < 80 and _SIMPLE_PATTERNS.match(stripped):
            logger.debug("Classifier: routine (greeting fast-path)")
            return "routine"

        # Fast-path: obvious coding cases
        if _COMPLEX_PATTERNS.search(stripped):
            logger.debug("Classifier: coding (keyword match)")
            return "coding"

        # Fast-path: short messages defaults to routine
        if len(stripped) < 100:
            logger.debug("Classifier: routine (short, no specific complex keywords)")
            return "routine"

        # Ambiguous: ask Haiku for a granular decision
        if self._claude is not None:
            try:
                result = await self._claude.complete(
                    messages=[
                        {
                            "role": "user",
                            "content": (
                                f"Classify this message into ONE category:\n"
                                f"ROUTINE: casual chat, greetings, short questions.\n"
                                f"SUMMARIZATION: asking to summarize text, emails, or documents.\n"
                                f"REASONING: complex planning, multi-step tasks, deep analysis.\n"
                                f"SAFETY: requesting system changes, file writes, or sensitive actions.\n"
                                f"CODING: writing or fixing code, scripts, or technical tasks.\n"
                                f"PERSONA: roleplay or specific character interaction.\n\n"
                                f"Reply with ONLY the category name.\n\n"
                                f'Message: """{stripped[:800]}"""'
                            ),
                        }
                    ],
                    model=None,  # uses settings.model_simple (Haiku)
                    system="You are an intent classifier. Reply only with the category name.",
                    max_tokens=10,
                )
                classification = result.strip().upper()
                if "SUMMARIZATION" in classification:
                    return "summarization"
                if "REASONING" in classification:
                    return "reasoning"
                if "SAFETY" in classification:
                    return "safety"
                if "CODING" in classification:
                    return "coding"
                if "PERSONA" in classification:
                    return "persona"
                
                return "routine"
            except Exception as e:
                logger.warning("Classifier granular call failed: %s", e)

        # Default to reasoning when uncertain (safe bet for capable models)
        return "reasoning"
