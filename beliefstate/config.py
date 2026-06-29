from typing import Any, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict, field_validator

DEFAULT_EXTRACT_PROMPT = """
You are a precise fact extraction engine. Extract every factual claim
that has been ESTABLISHED as true in this conversation — regardless of
what domain or topic it falls into.

Extract facts about ANYTHING: people, technical systems, plans,
decisions, constraints, budgets, tasks, preferences, locations,
configurations — everything. Do not limit yourself to one domain.

STEP 1 — IDENTIFY THE SUBJECT
Use the most specific, resolvable name. Never a pronoun.
  1. Actual name if stated: "Raj", "FastAPI", "the auth module"
  2. Role/type if name unknown: "Database", "Backend Framework"
  3. First-person user claims → "USER"
  4. Assistant self-claims → "ASSISTANT"
  5. Pronouns (it, they, that) → resolve to most recent entity.
     If unresolvable → OMIT the belief entirely.

STEP 2 — NORMALISE THE VALUE
  - Numbers: digits only (5000 not "five thousand")
  - Currency: ISO code + amount (USD 5000 not "$5,000")
  - Dates: ISO 8601 (2024-03-15 not "March 15th")
  - Tech names: official capitalisation (PostgreSQL, FastAPI, TypeScript)
  - Port numbers: integer (8080 not "port 8080")
  - Status: snake_case (in_progress, not_started, done, blocked)

STEP 3 — CLASSIFY
  confidence: 0.95–1.0 direct statement, 0.75–0.90 clear implication,
              0.50–0.70 soft statement ("I think we will use...")

  belief_type:
    "assertion" — new fact stated for first time
    "update"    — explicitly replaces prior statement
                  triggers: "actually", "instead", "let's switch",
                  "changed", "no longer", "we decided on X instead"

  is_hypothetical: true if conditional or speculative
    triggers: "if", "might", "could", "as an option", "potentially",
              "we may consider", "in case", "if we face"
    IMPORTANT: Store hypotheticals — do NOT skip them.
    They are useful context. Flag them so they can be weighted lower.

  category: one of identity | technical | planning | constraint | state
    identity:   name, location, role, preference, biographical
    technical:  framework, database, language, tool, config, version
    planning:   task, assignment, deadline, dependency, milestone
    constraint: budget, limit, requirement, rule, must/cannot
    state:      current status, what is built, what was tried

  source_quote: verbatim excerpt from original text, MAX 100 chars.
    Trim to the key phrase. Never the full sentence.

EXTRACT ALL of these when present:
  IDENTITY: names, locations, roles, preferences, biographical facts
  TECHNICAL: frameworks, databases, languages, tools, APIs, architecture
    patterns, deployment targets, version constraints, config values,
    coding standards, testing strategies, port numbers, env vars
  PLANNING: who owns what, deadlines, task status, dependencies,
    blockers, priorities, milestones, decisions made
  CONSTRAINTS: budget, performance, security, compliance requirements,
    non-negotiables, "must", "cannot", "required", "forbidden"
  STATE: current status of features, what is built vs planned,
    what has been decided vs open, what was tried and failed

DO NOT EXTRACT:
  - Pure questions not yet answered
  - Ideas not committed to ("we could maybe...")
  - Pleasantries and social exchange
  - Code output itself (function bodies, SQL, config files)
    BUT DO extract the decision that produced the code:
    "we will use async SQLAlchemy" is extractable;
    the SQLAlchemy code block is not.
  - Restating what was already said with no new information

OUTPUT FORMAT — return ONLY valid JSON array, no markdown, no explanation.
If no facts present, return [].
[
  {{
    "subject": "specific entity name — never a pronoun",
    "predicate": "the relation",
    "value": "normalised value",
    "confidence": 0.0,
    "belief_type": "assertion",
    "is_hypothetical": false,
    "category": "identity",
    "source": "user",
    "source_quote": "verbatim excerpt max 100 chars"
  }}
]

EXAMPLES:
Input: User: "I am Raj. Budget is $5k. Use FastAPI and PostgreSQL. Assign auth to Priya. If scaling issues, might add Redis."
Output:
[
  {{"subject":"USER","predicate":"name is","value":"Raj","confidence":0.99,"belief_type":"assertion","is_hypothetical":false,"category":"identity","source":"user","source_quote":"I am Raj"}},
  {{"subject":"Project","predicate":"budget is","value":"USD 5000","confidence":0.97,"belief_type":"assertion","is_hypothetical":false,"category":"constraint","source":"user","source_quote":"Budget is $5k"}},
  {{"subject":"Backend Framework","predicate":"is","value":"FastAPI","confidence":0.97,"belief_type":"assertion","is_hypothetical":false,"category":"technical","source":"user","source_quote":"Use FastAPI"}},
  {{"subject":"Database","predicate":"is","value":"PostgreSQL","confidence":0.97,"belief_type":"assertion","is_hypothetical":false,"category":"technical","source":"user","source_quote":"and PostgreSQL"}},
  {{"subject":"Auth Module","predicate":"assigned to","value":"Priya","confidence":0.95,"belief_type":"assertion","is_hypothetical":false,"category":"planning","source":"user","source_quote":"Assign auth to Priya"}},
  {{"subject":"Cache Layer","predicate":"might be added for","value":"scaling issues","confidence":0.60,"belief_type":"assertion","is_hypothetical":true,"category":"technical","source":"user","source_quote":"might add Redis"}}
]

Input: User: "Actually switch from PostgreSQL to SQLite."
Output:
[{{"subject":"Database","predicate":"is","value":"SQLite","confidence":0.97,"belief_type":"update","is_hypothetical":false,"category":"technical","source":"user","source_quote":"switch from PostgreSQL to SQLite"}}]

Input: "That sounds great!"
Output: []

Conversation to extract from:
{conversation}
"""

DEFAULT_EXTRACT_USER_PROMPT = DEFAULT_EXTRACT_PROMPT

DEFAULT_EXTRACT_ASSISTANT_PROMPT = DEFAULT_EXTRACT_PROMPT

DEFAULT_JUDGE_PROMPT = """Analyze the relationship between these two claims.

Premise: {premise}
Hypothesis: {hypothesis}

Determine if the hypothesis:
1. **contradicts** the premise (they cannot both be true)
2. **entails** the premise (if true, the premise is also true - they're semantically equivalent or the hypothesis is more specific)
3. is **neutral** (no clear relationship)

CRITICAL: Detect semantic equivalence carefully. For example:
- "USER likes Python" and "USER enjoys Python" = ENTAILMENT (same meaning)
- "USER lives in Paris" and "USER lives in France" = ENTAILMENT (specific location is Paris, which is in France)
- "USER has 5000 dollars" and "USER has USD 5000" = ENTAILMENT (same meaning, different phrasing)

Return ONLY a JSON object with keys 'relationship' ('contradiction', 'entailment', or 'neutral'), 'score' (float between 0.0 and 1.0 representing confidence), and 'reason' (string explanation).
Do not wrap in markdown.

Format:
{{"relationship": "entailment", "score": 0.95, "reason": "Both claims express the same preference for Python using different vocabulary"}}
"""


class TrackerConfig(BaseModel):
    """Configuration for the BeliefTracker."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Store settings
    store_type: str = Field(
        default="sqlite",
        description="Type of storage to use ('sqlite', 'redis', 'postgres').",
    )
    store_kwargs: Dict[str, Any] = Field(
        default_factory=dict, description="Additional kwargs for the store."
    )

    @field_validator("store_type")
    @classmethod
    def validate_store_type(cls, v: str) -> str:
        valid = {"sqlite", "redis", "postgres"}
        if v.lower() not in valid:
            raise ValueError(f"store_type must be one of {valid}, got '{v}'")
        return v.lower()

    # Detection settings
    similarity_threshold: float = Field(
        default=0.82, description="Threshold for embedding similarity."
    )
    contradiction_threshold: float = Field(
        default=0.70, description="Threshold for finding contradictions."
    )
    entailment_threshold: float = Field(
        default=0.85,
        description="Threshold for detecting semantic entailment (belief duplication). If new belief is entailed by existing belief with score >= this threshold, skip the new belief.",
    )

    # Prompts
    extract_prompt_template: str = Field(
        default=DEFAULT_EXTRACT_PROMPT, description="Prompt used to extract beliefs."
    )
    extract_user_prompt_template: str = Field(
        default=DEFAULT_EXTRACT_USER_PROMPT,
        description="Prompt used to extract beliefs from user messages.",
    )
    extract_assistant_prompt_template: str = Field(
        default=DEFAULT_EXTRACT_ASSISTANT_PROMPT,
        description="Prompt used to extract beliefs from assistant messages.",
    )
    judge_prompt_template: str = Field(
        default=DEFAULT_JUDGE_PROMPT,
        description="Prompt used to detect contradictions.",
    )

    # Task behavior
    enable_background_tasks: bool = Field(
        default=True, description="Run tracking async to avoid blocking."
    )

    # Internal override for the tracker
    internal_provider: Optional[Any] = Field(
        default=None, description="Explicit provider for tracker's internal LLM calls."
    )
    embed_provider: Optional[Any] = Field(
        default=None, description="Explicit provider for embedding generation."
    )
    embed_model: Optional[str] = Field(
        default=None, description="Model name to use for embeddings."
    )

    # Resilience settings
    retry_max_attempts: int = Field(
        default=5, description="Max retry attempts for LLM API calls."
    )
    retry_min_wait: float = Field(
        default=2.0, description="Minimum wait time between retries in seconds."
    )
    retry_max_wait: float = Field(
        default=30.0, description="Maximum wait time between retries in seconds."
    )
    retry_multiplier: float = Field(
        default=2.0, description="Multiplier for exponential backoff."
    )

    enable_circuit_breaker: bool = Field(
        default=True, description="Enable circuit breaker protection."
    )
    circuit_breaker_failure_threshold: int = Field(
        default=5, description="Number of failures before tripping circuit breaker."
    )
    circuit_breaker_recovery_timeout: float = Field(
        default=30.0, description="Cooldown time in seconds before attempting recovery."
    )

    # Pluggable dispatcher settings
    task_dispatcher_type: str = Field(
        default="asyncio",
        description="Task dispatcher type ('asyncio', 'sync', 'celery', 'rq').",
    )
    dispatcher_kwargs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arguments/instances for initializing dispatcher.",
    )

    # Belief storage limits
    max_beliefs: int = Field(
        default=50,
        description="Maximum number of beliefs to inject into prompts (prevents context window overflow).",
    )
    belief_sort_strategy: str = Field(
        default="confidence_recency",
        description="Strategy for selecting top N beliefs: 'confidence_recency' (high confidence + recent turns) | 'recency' (most recent turns) | 'confidence' (highest confidence)",
    )

    # Belief TTL settings
    enable_belief_ttl: bool = Field(
        default=False,
        description="Enable automatic pruning of old beliefs based on age.",
    )
    belief_max_age_seconds: int = Field(
        default=86400,
        description="Maximum age in seconds for a belief before pruning (only if enable_belief_ttl=True).",
    )
    belief_ttl_check_interval: int = Field(
        default=3600,
        description="How often (in seconds) to check for expired beliefs in SQLite.",
    )

    # Staleness scoring for session resumption
    enable_staleness_scoring: bool = Field(
        default=True,
        description="Enable staleness scoring to deprioritize old beliefs during session resumption.",
    )
    staleness_threshold: float = Field(
        default=0.1,
        description="Minimum staleness score (confidence / days_since_referenced) to inject a belief. Beliefs below this threshold are excluded.",
    )

    # Token-aware belief injection
    enable_token_aware_injection: bool = Field(
        default=True,
        description="Enable token-aware belief injection for very long conversations.",
    )
    belief_budget_tokens: int = Field(
        default=500,
        description="Maximum tokens reserved for belief injection in prompts. If belief summary exceeds this, use relevance-based filtering.",
    )

    # Judge timeout
    judge_timeout: float = Field(
        default=60.0,
        description="Timeout in seconds for LLM judge contradiction checks.",
    )

    # Confidence caps by source
    user_confidence_cap: float = Field(
        default=0.99,
        description="Maximum confidence for beliefs extracted from user messages.",
    )
    assistant_confidence_cap: float = Field(
        default=0.85,
        description="Maximum confidence for beliefs extracted from assistant responses.",
    )
