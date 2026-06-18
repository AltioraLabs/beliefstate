import logging
import math
import re
from typing import Any, List, Optional, Tuple
from beliefstate.config import TrackerConfig
from beliefstate.models import Belief
from beliefstate.adapters.base import ProviderAdapter
from beliefstate.store.base import Store

logger = logging.getLogger(__name__)

# Negation tokens that indicate a belief should bypass cosine similarity gate
# and go straight to LLM judge to prevent false positives
NEGATION_TOKENS = {
    "not",
    "don't",
    "doesn't",
    "didn't",
    "won't",
    "can't",
    "cannot",
    "shouldn't",
    "couldn't",
    "wouldn't",
    "never",
    "no",
    "none",
    "nobody",
    "nothing",
    "nowhere",
    "hate",
    "dislike",
    "detest",
    "don't like",
    "doesn't like",
    "stopped",
    "quit",
    "quit",
    "unlike",
    "opposite of",
    "contrary to",
    "contradicts",
    "no longer",
    "not any",
    "isn't",
    "aren't",
    "wasn't",
    "weren't",
}


def has_negation(text: str) -> bool:
    """Check if text contains negation tokens.
    
    Returns True if any negation token is found in the text (case-insensitive).
    Helps force negated beliefs to LLM judge to prevent cosine similarity false positives.
    """
    if not text:
        return False
    
    text_lower = text.lower()
    
    # Quick check for common negation patterns
    if "not " in text_lower or " not" in text_lower:
        return True
    
    # Check for contractions like don't, doesn't, etc.
    if "n't" in text_lower:
        return True
    
    # Check for negation tokens
    # Use word boundaries to avoid matching "nothing" in "something"
    for token in NEGATION_TOKENS:
        # Create pattern with word boundaries
        pattern = r"\b" + re.escape(token) + r"\b"
        if re.search(pattern, text_lower):
            return True
    
    return False


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two vectors.
    
    Returns 0.0 if vectors have mismatched dimensions to prevent silent corruption.
    """
    if not v1 or not v2:
        return 0.0
    
    # Guard against dimension mismatch
    if len(v1) != len(v2):
        logger.warning(
            f"Embedding dimension mismatch: {len(v1)} vs {len(v2)}. "
            "This may indicate a model upgrade. Returning 0.0 similarity."
        )
        return 0.0
    
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0.0 or mag2 == 0.0:
        return 0.0
    return dot / (mag1 * mag2)


class ContradictionDetector:
    def __init__(
        self,
        adapter: ProviderAdapter,
        store: Store,
        config: TrackerConfig,
        judge: Optional[Any] = None,
    ):
        self.adapter = adapter
        self.store = store
        self.config = config
        if judge:
            self.judge = judge
        else:
            from beliefstate.judge import LLMJudge

            self.judge = LLMJudge(adapter, config)

    async def detect(
        self, session_id: str, new_beliefs: List[Belief]
    ) -> List[Tuple[Belief, Belief, float, str]]:
        """Detect contradictions between new beliefs and existing store.
        
        Checks for embedding model consistency to prevent silent dimension mismatch errors.
        """
        contradictions = []

        for new_b in new_beliefs:
            if not new_b.embedding:
                continue

            # Database-side vector search for top candidate beliefs
            matched_beliefs = await self.store.search_beliefs(
                session_id=session_id,
                embedding=new_b.embedding,
                threshold=self.config.similarity_threshold,
                limit=5,
            )

            for old_b in matched_beliefs:
                # Guard against embedding model mismatch
                if (
                    old_b.embedding_model
                    and new_b.embedding_model
                    and old_b.embedding_model != new_b.embedding_model
                ):
                    logger.warning(
                        f"Embedding model mismatch: old='{old_b.embedding_model}' vs new='{new_b.embedding_model}'. "
                        f"Belief may be from a different embedding version. Skipping comparison."
                    )
                    continue

                is_contradiction, score, reason = await self.judge.check(old_b, new_b)
                if is_contradiction:
                    contradictions.append((old_b, new_b, score, reason))

        return contradictions

    async def detect_with_deduplication(
        self, session_id: str, new_beliefs: List[Belief]
    ) -> Tuple[List[Tuple[Belief, Belief, float, str]], List[Belief]]:
        """Detect contradictions AND deduplicate entailed beliefs.
        
        Returns:
            - List of contradictions (old, new, score, reason)
            - List of new beliefs that are entailed by existing beliefs (duplicates to skip)
        
        Entailment check: if judge returns relationship="entailment" with score >= entailment_threshold,
        the new belief is semantically entailed by the old belief and should be skipped (it's a duplicate).
        
        Negation check: if belief contains negation tokens, bypasses cosine similarity gate and goes
        straight to LLM judge to prevent false positives (e.g., "likes X" vs "doesn't like X").
        
        Guards against embedding dimension mismatch: if old and new beliefs have
        different embedding dimensions, skips cosine similarity check and goes
        straight to LLM judge to avoid silent corruption.
        """
        contradictions = []
        duplicates_to_skip = []

        for new_b in new_beliefs:
            if not new_b.embedding:
                continue

            # Check if the new belief contains negation - if so, bypass cosine gate
            new_b_text = f"{new_b.predicate} {new_b.value}"
            has_new_negation = has_negation(new_b_text)

            # Database-side vector search for top candidate beliefs
            matched_beliefs = await self.store.search_beliefs(
                session_id=session_id,
                embedding=new_b.embedding,
                threshold=self.config.similarity_threshold,
                limit=5,
            )

            for old_b in matched_beliefs:
                # Guard against embedding model mismatch
                if (
                    old_b.embedding_model
                    and new_b.embedding_model
                    and old_b.embedding_model != new_b.embedding_model
                ):
                    logger.warning(
                        f"Embedding model mismatch: old='{old_b.embedding_model}' vs new='{new_b.embedding_model}'. "
                        f"Belief may be from a different embedding version. Skipping vector comparison, using LLM judge instead."
                    )
                    # Skip cosine gate entirely, go straight to LLM judge
                    is_contradiction, score, reason = await self.judge.check(old_b, new_b)
                    if is_contradiction:
                        contradictions.append((old_b, new_b, score, reason))
                    elif reason and "entailment" in reason.lower() and score >= self.config.entailment_threshold:
                        logger.debug(
                            f"Detected entailment (via model mismatch fallback): '{new_b.value}' entailed by '{old_b.value}' "
                            f"(score: {score:.2f}). Skipping duplicate."
                        )
                        duplicates_to_skip.append(new_b)
                    continue

                # Guard against embedding dimension mismatch
                if old_b.embedding_dim and new_b.embedding_dim and old_b.embedding_dim != new_b.embedding_dim:
                    logger.warning(
                        f"Embedding dimension mismatch for '{old_b.subject}': "
                        f"old={old_b.embedding_dim}D vs new={new_b.embedding_dim}D. "
                        f"This likely indicates embedding model upgrade. Skipping vector comparison, using LLM judge instead."
                    )
                    # Skip cosine gate entirely, go straight to LLM judge
                    is_contradiction, score, reason = await self.judge.check(old_b, new_b)
                    if is_contradiction:
                        contradictions.append((old_b, new_b, score, reason))
                    elif reason and "entailment" in reason.lower() and score >= self.config.entailment_threshold:
                        logger.debug(
                            f"Detected entailment (via dimension mismatch fallback): '{new_b.value}' entailed by '{old_b.value}' "
                            f"(score: {score:.2f}). Skipping duplicate."
                        )
                        duplicates_to_skip.append(new_b)
                    continue

                # Check for negation in either belief - if found, bypass cosine gate
                old_b_text = f"{old_b.predicate} {old_b.value}"
                has_old_negation = has_negation(old_b_text)
                
                if has_new_negation or has_old_negation:
                    logger.debug(
                        f"Negation detected in belief (new: {has_new_negation}, old: {has_old_negation}). "
                        f"Bypassing cosine similarity gate, going straight to LLM judge."
                    )
                    # Skip cosine gate, use LLM judge directly to avoid false positives
                    is_contradiction, score, reason = await self.judge.check(old_b, new_b)
                    if is_contradiction:
                        contradictions.append((old_b, new_b, score, reason))
                        logger.debug(f"Detected negation-related contradiction: '{old_b.value}' vs '{new_b.value}'")
                    elif reason and "entailment" in reason.lower() and score >= self.config.entailment_threshold:
                        logger.debug(
                            f"Detected entailment (negation path): '{new_b.value}' entailed by '{old_b.value}' "
                            f"(score: {score:.2f}). Skipping duplicate."
                        )
                        duplicates_to_skip.append(new_b)
                    continue

                # Normal path: cosine similarity check
                is_contradiction, score, reason = await self.judge.check(old_b, new_b)
                
                if is_contradiction:
                    contradictions.append((old_b, new_b, score, reason))
                    logger.debug(f"Detected contradiction: '{old_b.value}' vs '{new_b.value}' (score: {score:.2f})")
                    
                # Check for entailment - new belief is semantically entailed by existing belief
                # The judge returns relationship types: "contradiction", "entailment", "neutral"
                # If the judge explicitly identified entailment, use that. Otherwise fall back to checking reason string.
                elif score >= self.config.entailment_threshold:
                    # Check if reason/judge response indicates entailment relationship
                    if reason and "entailment" in reason.lower():
                        logger.debug(
                            f"Detected entailment: '{new_b.value}' semantically entailed by '{old_b.value}' "
                            f"(score: {score:.2f}). Skipping duplicate."
                        )
                        duplicates_to_skip.append(new_b)
                        break

        return contradictions, duplicates_to_skip
