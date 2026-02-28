"""
Message complexity classifier.
Decides whether to route to a simple/cheap model or a complex/capable one.

Uses heuristic-only classification for performance (no API calls).
The cost of occasional misrouting is far less than the 300-800ms latency
penalty of a classifier API call on every ambiguous message.

Results are cached (TTL=5 min, max 256 entries) on a normalised key so minor
rephrasing and repeated questions benefit from caching.
"""

import hashlib
import logging
import re
import time
from typing import Literal

logger = logging.getLogger(__name__)

# Keywords that strongly signal a complex, agentic or tool-use task
_COMPLEX_PATTERNS = re.compile(
    r"""
    (?xi)
    \bwrite\b.*\b(?:script|function|class|file|test|code)\b
    | \bcreate\b.*\b(?:project|module|app|api|bot|function|script|class|plan|goal)\b
    | \brefactor\b | \bdebug\b | \bfix\s+(?:the|this|a|my)\b
    | \bbuild\b | \bimplement\b | \bgenerate\s+(?:code|a)\b
    | \bcommit\b | \bgit\b | \bdeploy\b | \bpush\b | \bpull\b
    | \.py\b | \.ts\b | \.js\b | \.sh\b | \.json\b | \.yaml\b | \.md\b
    | ```                                   # code fences
    | (?:step\s+\d|first.*then.*finally)    # multi-step instructions
    | /board | /breakdown | /research       # tool-intensive commands
    | \bAPI\b | \bSDK\b | \bCLI\b           # technical acronyms
    | \bfunction\b | \bclass\b | \bmethod\b | \bvariable\b
    | \berror\b | \bbug\b | \bexception\b | \bcrash\b
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Messages that are clearly simple greetings or short questions
_SIMPLE_PATTERNS = re.compile(
    r"""
    ^(?:
        hi|hello|hey|g'day|morning|afternoon|evening
        | thanks?|thank\s+you|cheers|ta
        | ok|okay|k|cool|great|sure|yes|no|nope|yep|yeah|nah
        | good|nice|awesome|perfect|brilliant|lovely
        | bye|goodbye|later|cya|see\s+you
        | what(?:'s|\s+is)\s+up
        | how(?:'s|\s+it|\s+are\s+you)
    )\b
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Summarisation signals
_SUMMARIZE_PATTERNS = re.compile(
    r"""
    \b(?:
        summarize|summarise|summary
        | tldr|tl;dr
        | recap|recapitulate
        | sum\s+up|summar(?:y|ize|ise)
        | brief(?:ly)?|briefly\s+explain
        | overview|digest|synopsis
        | key\s+points|main\s+points|highlights
        | condense|shorten
    )\b
    | \bwhat(?:'s|\s+is)\s+(?:in|the\s+gist\s+of)\b
    | \bgive\s+me\s+(?:a\s+)?(?:quick|brief)\b
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Reasoning / planning signals
_REASONING_PATTERNS = re.compile(
    r"""
    \b(?:
        plan|planning|strategy|strategize|strategise
        | analyse|analyze|analysis
        | think\s+through|walk\s+me\s+through|explain\s+how
        | pros?\s+and\s+cons?|trade-?offs?|advantages?\s+and\s+disadvantages?
        | compare|comparison|contrast|versus|vs\.?
        | evaluate|assessment|weigh\s+(?:up|the)
        | should\s+I|help\s+me\s+decide|what\s+do\s+you\s+think
        | recommend|suggestion|advice|advise
        | consider|considering|options?
        | best\s+(?:way|approach|practice|option)
        | how\s+(?:should|would|could)\s+(?:I|we)
    )\b
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Safety-sensitive patterns (file operations, system changes)
_SAFETY_PATTERNS = re.compile(
    r"""
    \b(?:
        delete|remove|erase|destroy
        | overwrite|replace\s+(?:the|all|my)
        | format|wipe|clear\s+(?:the|all|my)
        | send\s+(?:email|message|money)
        | transfer|payment|purchase|buy
        | password|credential|secret|token|key
        | admin|root|sudo|permission
        | unsubscribe|cancel\s+(?:my|the)
    )\b
    """,
    re.VERBOSE | re.IGNORECASE,
)

# Persona / roleplay signals
_PERSONA_PATTERNS = re.compile(
    r"""
    \b(?:
        roleplay|role-?play|pretend|act\s+as|be\s+(?:a|my)
        | character|persona|voice
        | speak\s+(?:like|as)|talk\s+(?:like|as)
        | impersonate|imitate
    )\b
    | ^(?:you\s+are|imagine\s+you(?:'re|\s+are))
    """,
    re.VERBOSE | re.IGNORECASE,
)

ClassificationResult = Literal[
    "routine",         # Short interactive messages, greetings
    "summarization",   # Email summaries, doc summaries
    "reasoning",       # Planning, multi-step tasks, deep analysis
    "safety",          # File writes, financial actions (if any)
    "coding",          # Scripting, code generation
    "persona",         # Roleplay
]

# ---------------------------------------------------------------------------
# In-process classification cache
# ---------------------------------------------------------------------------
_CACHE_TTL = 300        # seconds
_CACHE_MAX = 256        # entries; simple FIFO eviction when full

_cache: dict[str, tuple[ClassificationResult, float]] = {}  # key -> (result, ts)


def _normalise(text: str) -> str:
    """Lowercase, collapse whitespace, strip punctuation for a stable cache key."""
    text = text.lower().strip()
    text = re.sub(r"[^\w\s]", "", text)
    return re.sub(r"\s+", " ", text)


def _cache_key(text: str) -> str:
    return hashlib.md5(_normalise(text).encode(), usedforsecurity=False).hexdigest()


def _cache_get(key: str) -> ClassificationResult | None:
    entry = _cache.get(key)
    if entry and (time.monotonic() - entry[1]) < _CACHE_TTL:
        return entry[0]
    _cache.pop(key, None)
    return None


def _cache_set(key: str, result: ClassificationResult) -> None:
    if len(_cache) >= _CACHE_MAX:
        # Evict oldest entry
        oldest = min(_cache, key=lambda k: _cache[k][1])
        _cache.pop(oldest, None)
    _cache[key] = (result, time.monotonic())


class MessageClassifier:
    """
    Classify messages into categories for optimal model routing.
    
    Uses heuristic-only classification for performance. No API calls are made,
    eliminating the 300-800ms latency penalty that would otherwise occur for
    ambiguous messages. The capable model (Sonnet) handles all categories well,
    so the cost of occasional misrouting is minimal.
    """

    def __init__(self, claude_client=None) -> None:
        # claude_client kept for API compatibility but no longer used
        self._claude = claude_client

    async def classify(self, text: str, user_id: int | None = None, db=None) -> ClassificationResult:
        """Return a task category for the given message text."""
        stripped = text.strip()
        key = _cache_key(stripped)

        cached = _cache_get(key)
        if cached is not None:
            logger.debug("Classifier: %s (cache hit)", cached)
            return cached

        # Heuristic-only classification (no API calls for latency)
        result = self._classify_heuristic(stripped)
        _cache_set(key, result)
        return result

    def _classify_heuristic(self, stripped: str) -> ClassificationResult:
        """
        Classify using heuristics only. Order matters: more specific patterns
        are checked before general ones.
        """
        text_len = len(stripped)
        
        # Very short messages with greeting patterns -> routine
        if text_len < 80 and _SIMPLE_PATTERNS.match(stripped):
            logger.debug("Classifier: routine (greeting)")
            return "routine"
        
        # Safety-sensitive operations (check early for security)
        if _SAFETY_PATTERNS.search(stripped):
            logger.debug("Classifier: safety (sensitive operation)")
            return "safety"
        
        # Persona / roleplay requests
        if _PERSONA_PATTERNS.search(stripped):
            logger.debug("Classifier: persona (roleplay)")
            return "persona"
        
        # Coding / technical tasks
        if _COMPLEX_PATTERNS.search(stripped):
            logger.debug("Classifier: coding (technical)")
            return "coding"
        
        # Summarisation requests
        if _SUMMARIZE_PATTERNS.search(stripped):
            logger.debug("Classifier: summarization")
            return "summarization"
        
        # Reasoning / planning / analysis
        if _REASONING_PATTERNS.search(stripped):
            logger.debug("Classifier: reasoning (planning)")
            return "reasoning"
        
        # Short messages without specific keywords -> routine
        # Increased threshold from 100 to 150 chars for better coverage
        if text_len < 150:
            logger.debug("Classifier: routine (short message)")
            return "routine"
        
        # Medium-length messages (150-300 chars) without keywords -> routine
        # These are typically conversational questions
        if text_len < 300:
            logger.debug("Classifier: routine (conversational)")
            return "routine"
        
        # Longer messages default to reasoning (capable model handles well)
        logger.debug("Classifier: reasoning (default for long message)")
        return "reasoning"

    # Keep the old method signature for backwards compatibility
    async def _classify_uncached(self, stripped: str, user_id: int | None = None, db=None) -> ClassificationResult:
        """Deprecated: Use _classify_heuristic instead."""
        return self._classify_heuristic(stripped)
