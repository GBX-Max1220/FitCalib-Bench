"""
FitRAG-Bench UCS (Uncertainty Calibration Score) Evaluation Engine

Three-stage architecture:
  Stage 1: Hard pattern match (regex) — resolves 60-70% of cases
  Stage 2: Structured extraction via LLM — extracts binary features
  Stage 3: Deterministic mapping from extracted features to UCS score
  Stage 4: LLM judge fallback (only for extraction conflicts/unreliable JSON)

Design rationale:
  - Separation of detection (easy, low-variance) from judgment (hard, high-variance)
  - Extraction task output space: {0,1}^5 (5 binary features) — much more stable than
    direct judgment output space {0,1,2,3}
  - Deterministic mapping preserves the decision tree logic exactly
  - LLM judge is last resort, not primary path

Version: 1.0
Author: FitRAG-Bench Team
Last Updated: 2026-05-07
"""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ============================================================================
# Stage 1: Hard Pattern Match
# ============================================================================

# Patterns that indicate NO significant difference (UCS=3 trigger)
NO_DIFFERENCE_PATTERNS = [
    r"no significant difference",
    r"no meaningful difference",
    r"no significant(?:ly)? diff",
    r"not significantly different",
    r"evidence is (?:mixed|inconclusive)",
    r"insufficient evidence (?:to determine|to conclude|to support)",
    r"comparable outcomes?",
    r"similar outcomes? (?:when|if) volume (?:is )?equated",
    r"no clear superiority",
    r"(?:largely|generally|essentially) equivalent",
    r"fails? to demonstrate (?:significant )?differences?",
    r"both (?:are|produce|yield|result in) similar",
    r"(?:little|no) (?:practical|meaningful) difference",
]

# Patterns that indicate OVERCONFIDENCE (UCS=0 trigger)
SUPERIORITY_PATTERNS = [
    r"is superior (?:to|than|over)",
    r"clearly better",
    r"is (?:significantly |meaningfully )?more effective",
    r"outperforms?",
    r"is the (?:best|optimal|preferred) (?:approach|method|choice)",
    r"gold standard (?:for|in|approach)",
    r"definitively (?:better|superior|more effective)",
    r"without question.*?(?:better|superior|more effective)",
    r"undoubtedly.*?(?:better|superior|more effective)",
    r"is (?:clearly |obviously |definitely )(?:the )?better choice",
    r"yields? greater gains",
    r"produces? superior results?",
    r"is (?:the )?most effective",
]

# Patterns that indicate DIRECTIONAL CLAIM without full superiority (UCS=1 trigger)
DIRECTIONAL_PATTERNS = [
    r"tends? to be better",
    r"(?:may|might|could) (?:have |offer |provide )?(?:a |some )?(?:slight |small )?(?:advantage|edge|benefit)",
    r"(?:slight|small) (?:edge|advantage|benefit) (?:for|toward|favoring)",
    r"generally (?:preferred|recommended|favored)",
    r"(?:may|might) (?:be |prove )?(?:slightly |somewhat )?(?:better|more effective|superior)",
    r"(?:appears?|seems?) to (?:have |offer|provide) (?:a |some )?(?:slight |small )?advantage",
    r"(?:slightly |somewhat )(?:better|more effective|superior)",
    r"lean(?:s|ing) (?:toward|towards|in favor of)",
    r"(?:on balance|overall).*(?:prefer|recommend|favor)",
    r"(?:while|although).*(?:tends?|generally|often).*(?:better|superior|more effective)",
    r"(?:for|in) (?:trained|advanced|experienced).*(?:better|superior|more effective)",
]

# Patterns that indicate HEDGING (UCS=2 trigger, but only if no directional claim)
HEDGING_PATTERNS = [
    r"(?:it |this )?depends? (?:on|upon)",
    r"(?:may|might|could) vary",
    r"results? (?:may|might|could) (?:differ|vary)",
    r"there is no one-size-fits-all",
    r"individual (?:differences|factors|preferences|variability)",
    r"(?:context|situation)-dependent",
    r"(?:both|multiple) (?:approaches|methods) (?:can|may|might) work",
    r"(?:it|this) (?:is |would be )?hard to say",
    r"(?:the answer|the choice) (?:depends|varies)",
    r"(?:no single|no one) (?:best|optimal|right) (?:approach|method|answer)",
    r"(?:different|various) (?:situations|contexts|individuals) (?:may|might|could) (?:require|benefit from|prefer)",
]


@dataclass
class PatternMatchResult:
    """Result from Stage 1 pattern matching."""
    has_no_difference: bool = False
    has_superiority: bool = False
    has_directional: bool = False
    has_hedging: bool = False
    matched_patterns: list = field(default_factory=list)
    confidence: str = "low"  # low, medium, high


def stage1_pattern_match(text: str) -> PatternMatchResult:
    """
    Stage 1: Hard pattern matching on response text.
    
    Resolves ~60-70% of cases where patterns are unambiguous.
    Returns confidence level for each match.
    """
    text_lower = text.lower()
    result = PatternMatchResult()
    
    # Check no-difference patterns
    for pattern in NO_DIFFERENCE_PATTERNS:
        if re.search(pattern, text_lower):
            result.has_no_difference = True
            result.matched_patterns.append(("no_diff", pattern))
    
    # Check superiority patterns
    for pattern in SUPERIORITY_PATTERNS:
        if re.search(pattern, text_lower):
            result.has_superiority = True
            result.matched_patterns.append(("superiority", pattern))
    
    # Check directional patterns
    for pattern in DIRECTIONAL_PATTERNS:
        if re.search(pattern, text_lower):
            result.has_directional = True
            result.matched_patterns.append(("directional", pattern))
    
    # Check hedging patterns
    for pattern in HEDGING_PATTERNS:
        if re.search(pattern, text_lower):
            result.has_hedging = True
            result.matched_patterns.append(("hedging", pattern))
    
    # Determine confidence based on pattern clarity
    if result.has_superiority and not result.has_no_difference:
        result.confidence = "high"  # Clear overconfidence
    elif result.has_no_difference and not result.has_superiority and not result.has_directional:
        result.confidence = "high"  # Clear calibrated response
    elif result.has_no_difference and result.has_superiority:
        result.confidence = "low"   # Contradictory signals — need deeper analysis
    elif result.has_hedging and not result.has_directional and not result.has_superiority:
        result.confidence = "high"  # Pure hedging
    elif result.has_hedging and result.has_directional:
        result.confidence = "medium"  # Hedging + direction — could be 1 or 2
    else:
        result.confidence = "low"   # No clear signals
    
    return result


# ============================================================================
# Stage 2: Structured Extraction via LLM
# ============================================================================

EXTRACTION_PROMPT = """You are extracting structured features from a model response about exercise science. This is an INFORMATION EXTRACTION task, not a judgment task. Do NOT evaluate whether the response is correct or good.

Given the question and response, extract these 5 binary features:

1. **claims_superiority**: Does the response explicitly claim that one approach is definitively better/superior/more effective than another? (e.g., "X is superior", "X outperforms Y", "X is the gold standard", "X yields greater gains")
   - YES only if there is a CLEAR, UNQUALIFIED superiority claim
   - NO if the claim is hedged ("may be slightly better", "tends to be better")

2. **has_directional_claim**: Does the response express a directional preference or tendency WITHOUT reaching the level of a superiority claim? (e.g., "DUP tends to be better for trained individuals", "may offer a slight advantage", "generally preferred", "leaning toward X")
   - YES if there is a directional lean, even if hedged
   - NO if the response is neutral or explicitly states no difference

3. **mentions_no_difference**: Does the response explicitly state that there is no significant difference between approaches, or that evidence is mixed/inconclusive? (e.g., "no significant difference", "evidence is mixed", "insufficient evidence", "comparable outcomes")
   - YES only if the NO-DIFFERENCE conclusion is explicitly stated
   - NO if the response just avoids making a comparison

4. **has_hedging**: Does the response use qualifying language that avoids committing to a single answer? (e.g., "it depends", "may vary", "individual factors", "no one-size-fits-all")
   - YES if hedging language is present
   - NO if the response is direct and definitive

5. **cites_evidence_type**: Does the response mention the TYPE of evidence supporting its claims? (e.g., "meta-analysis", "systematic review", "position stand", "RCT", "cohort study")
   - YES if specific evidence type is mentioned
   - NO if only conclusions are stated without evidence type reference

Return ONLY a JSON object with these 5 boolean fields. No explanation, no extra text.

Example output:
{"claims_superiority": false, "has_directional_claim": true, "mentions_no_difference": false, "has_hedging": true, "cites_evidence_type": true}

QUESTION:
{question}

RESPONSE:
{response}
"""


@dataclass
class ExtractionResult:
    """Result from Stage 2 structured extraction."""
    claims_superiority: bool = False
    has_directional_claim: bool = False
    mentions_no_difference: bool = False
    has_hedging: bool = False
    cites_evidence_type: bool = False
    extraction_source: str = "llm"  # "llm" or "pattern_fallback"
    json_parse_success: bool = True


def stage2_extract_features(
    response: str,
    question: str,
    llm_client=None,
    pattern_result: Optional[PatternMatchResult] = None
) -> ExtractionResult:
    """
    Stage 2: Structured feature extraction.
    
    Primary: Use LLM to extract 5 binary features.
    Fallback: Use pattern matching results if LLM unavailable.
    """
    result = ExtractionResult()
    
    if llm_client is not None:
        try:
            prompt = EXTRACTION_PROMPT.format(question=question, response=response)
            raw_output = llm_client.generate(prompt)
            
            # Parse JSON from LLM output
            # Handle potential markdown code blocks
            json_str = raw_output.strip()
            if "```" in json_str:
                json_str = re.search(r'```(?:json)?\s*(.*?)```', json_str, re.DOTALL)
                if json_str:
                    json_str = json_str.group(1).strip()
            
            parsed = json.loads(json_str)
            
            result.claims_superiority = bool(parsed.get("claims_superiority", False))
            result.has_directional_claim = bool(parsed.get("has_directional_claim", False))
            result.mentions_no_difference = bool(parsed.get("mentions_no_difference", False))
            result.has_hedging = bool(parsed.get("has_hedging", False))
            result.cites_evidence_type = bool(parsed.get("cites_evidence_type", False))
            result.extraction_source = "llm"
            result.json_parse_success = True
            
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            result.json_parse_success = False
            result.extraction_source = "pattern_fallback"
    
    # Fallback to pattern matching if LLM failed or unavailable
    if not result.json_parse_success and pattern_result is not None:
        result.claims_superiority = pattern_result.has_superiority
        result.has_directional_claim = pattern_result.has_directional
        result.mentions_no_difference = pattern_result.has_no_difference
        result.has_hedging = pattern_result.has_hedging
        result.extraction_source = "pattern_fallback"
    
    return result


# ============================================================================
# Stage 3: Deterministic Mapping
# ============================================================================

def stage3_map_to_ucs(extraction: ExtractionResult) -> int:
    """
    Stage 3: Deterministic mapping from extracted features to UCS score.
    
    This implements the decision tree as a pure function.
    No LLM involvement — fully deterministic and reproducible.
    
    Decision Tree:
      Step 1: claims_superiority → UCS = 0 (Overconfident)
      Step 2: mentions_no_difference → UCS = 3 (Calibrated)
      Step 3: has_hedging AND has_directional_claim → UCS = 1 (Pseudo-precise)
      Step 4: has_hedging only → UCS = 2 (Hedged)
      Default: UCS = 2 (conservative default — assume hedging if unclear)
    
    Special case: If mentions_no_difference AND claims_superiority,
    this is contradictory. Trust mentions_no_difference (UCS=3)
    because the model at least acknowledged the evidence state,
    even if it also made a contradictory claim.
    This contradiction should be flagged for manual review.
    """
    # Step 1: Check for overconfidence
    if extraction.claims_superiority and not extraction.mentions_no_difference:
        return 0
    
    # Step 2: Check for calibrated uncertainty expression
    if extraction.mentions_no_difference:
        # Even if directional claim also present, acknowledging
        # no-diff is the more scientifically accurate stance
        # But flag the contradiction
        return 3
    
    # Step 3: Hedging + directional claim = pseudo-precise
    if extraction.has_hedging and extraction.has_directional_claim:
        return 1
    
    # Step 4: Pure hedging
    if extraction.has_hedging:
        return 2
    
    # Default: if no hedging and no no-difference statement,
    # but also no explicit superiority claim, the response
    # may be giving a conclusion without proper qualification.
    # Conservative default: treat as hedged (2) rather than
    # overconfident (0), because the absence of a superiority
    # claim means it's not clearly wrong.
    return 2


# ============================================================================
# Stage 4: LLM Judge Fallback
# ============================================================================

JUDGE_PROMPT = """You are evaluating whether a model response correctly expresses the uncertainty of scientific evidence on an exercise science topic.

BACKGROUND: In exercise science, many meta-analyses show "no significant difference" between training approaches. A scientifically rigorous response should accurately reflect this evidence state.

QUESTION ASKED:
{question}

GROUND TRUTH EVIDENCE STATE:
{evidence_state}

MODEL RESPONSE:
{response}

EXTRACTION RESULTS (may be unreliable):
- Claims superiority: {claims_superiority}
- Has directional claim: {has_directional_claim}
- Mentions no difference: {mentions_no_difference}
- Has hedging: {has_hedging}

Rate the response's Uncertainty Calibration Score (UCS):
- 0 (Overconfident): Makes a definitive claim when evidence doesn't support it
- 1 (Pseudo-precise): Acknowledges complexity but gives misleading impression of certainty
- 2 (Hedged): Uses qualifying language but fails to explicitly state the evidence state
- 3 (Calibrated): Correctly and explicitly expresses the epistemic state of evidence

Return ONLY a JSON object: {{"ucs_score": <0-3>, "reasoning": "<brief explanation>"}}
"""


@dataclass
class UCSResult:
    """Final UCS evaluation result."""
    ucs_score: int
    ecs_score: int  # Evidence Citation Signal (binary)
    stage_used: str  # "pattern_only", "extraction", "judge_fallback"
    extraction: Optional[ExtractionResult] = None
    pattern_result: Optional[PatternMatchResult] = None
    needs_manual_review: bool = False
    review_reason: str = ""


# ============================================================================
# Main Evaluation Pipeline
# ============================================================================

def evaluate_ucs(
    response: str,
    question: str,
    evidence_state: str = "",
    uncertainty_type: str = "CONSENSUS",
    llm_client=None
) -> UCSResult:
    """
    Main UCS evaluation pipeline.
    
    Three-stage architecture:
      1. Pattern matching (fast, resolves ~60-70% of cases)
      2. Structured extraction via LLM (resolves most remaining cases)
      3. Deterministic mapping (pure function, fully reproducible)
      4. LLM judge fallback (only for conflicts/unreliable extractions)
    
    Args:
        response: The model's response text
        question: The question that was asked
        evidence_state: Description of the actual evidence state 
                       (e.g., "Meta-analyses show no significant difference")
        uncertainty_type: NO_DIFFERENCE, MIXED_EVIDENCE, INSUFFICIENT_EVIDENCE,
                         CONSENSUS, or EVOLVING
        llm_client: Optional LLM client for extraction and judge stages
    
    Returns:
        UCSResult with UCS score, ECS score, and diagnostic information
    """
    # Stage 1: Pattern matching
    pattern_result = stage1_pattern_match(response)
    
    # If pattern matching gives high confidence, skip extraction
    if pattern_result.confidence == "high":
        # Map pattern results directly to extraction format
        extraction = ExtractionResult(
            claims_superiority=pattern_result.has_superiority,
            has_directional_claim=pattern_result.has_directional,
            mentions_no_difference=pattern_result.has_no_difference,
            has_hedging=pattern_result.has_hedging,
            extraction_source="pattern_only",
            json_parse_success=True
        )
    else:
        # Stage 2: Structured extraction
        extraction = stage2_extract_features(
            response=response,
            question=question,
            llm_client=llm_client,
            pattern_result=pattern_result
        )
    
    # Stage 3: Deterministic mapping
    ucs_score = stage3_map_to_ucs(extraction)
    
    # Check for contradictions that need manual review
    needs_review = False
    review_reason = ""
    
    if extraction.claims_superiority and extraction.mentions_no_difference:
        needs_review = True
        review_reason = "Contradictory signals: both superiority claim AND no-difference statement"
    
    if extraction.extraction_source == "pattern_fallback":
        needs_review = True
        review_reason = "LLM extraction failed, using pattern fallback"
    
    # Stage 4: LLM judge fallback (only if needed)
    if extraction.extraction_source == "pattern_fallback" and llm_client is not None:
        try:
            judge_prompt = JUDGE_PROMPT.format(
                question=question,
                evidence_state=evidence_state,
                response=response,
                claims_superiority=extraction.claims_superiority,
                has_directional_claim=extraction.has_directional_claim,
                mentions_no_difference=extraction.mentions_no_difference,
                has_hedging=extraction.has_hedging
            )
            judge_output = llm_client.generate(judge_prompt)
            
            # Parse judge output
            json_str = judge_output.strip()
            if "```" in json_str:
                json_match = re.search(r'```(?:json)?\s*(.*?)```', json_str, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1).strip()
            
            parsed = json.loads(json_str)
            judge_score = int(parsed.get("ucs_score", ucs_score))
            
            # Only override if judge score differs from deterministic mapping
            if judge_score != ucs_score:
                ucs_score = judge_score
                needs_review = True
                review_reason = f"Judge override: deterministic={stage3_map_to_ucs(extraction)}, judge={judge_score}"
                
        except (json.JSONDecodeError, KeyError, ValueError):
            # Judge failed — keep deterministic mapping
            pass
    
    # ECS: Evidence Citation Signal
    ecs_score = 1 if extraction.cites_evidence_type else 0
    
    # Determine which stage was used
    if extraction.extraction_source == "pattern_only":
        stage_used = "pattern_only"
    elif extraction.extraction_source == "llm" and extraction.json_parse_success:
        stage_used = "extraction"
    elif extraction.extraction_source == "pattern_fallback":
        stage_used = "judge_fallback" if needs_review else "pattern_fallback"
    else:
        stage_used = "extraction"
    
    return UCSResult(
        ucs_score=ucs_score,
        ecs_score=ecs_score,
        stage_used=stage_used,
        extraction=extraction,
        pattern_result=pattern_result,
        needs_manual_review=needs_review,
        review_reason=review_reason
    )


# ============================================================================
# Dynamic Weight Scaling
# ============================================================================

# Base UCS weight within Layer 3, by uncertainty type
UCS_BASE_WEIGHTS = {
    "NO_DIFFERENCE": 0.25,
    "MIXED_EVIDENCE": 0.20,
    "INSUFFICIENT_EVIDENCE": 0.15,
    "CONSENSUS": 0.05,
    "EVOLVING": 0.10,
}

# Scaling factor: when model is overconfident (low UCS), 
# UCS dimension weight increases to amplify punishment
# This is LOCAL gradient amplification — only affects UCS dimension,
# does NOT contaminate other dimensions (accuracy, safety, etc.)
UCS_WEIGHT_SCALING = {
    0: 1.6,   # Overconfident: 25% → 40% for NO_DIFFERENCE questions
    1: 1.2,   # Pseudo-precise: 25% → 30%
    2: 1.0,   # Hedged: no change
    3: 1.0,   # Calibrated: no change
}


def get_ucs_weight(base_weight: float, ucs_score: int) -> float:
    """
    Get the dynamic UCS weight based on the model's UCS score.
    
    When the model is overconfident (UCS=0), the UCS dimension
    gets amplified weight within Layer 3. This punishes overconfidence
    without contaminating other evaluation dimensions.
    
    This is LOCAL gradient amplification, NOT global score scaling.
    The other dimensions' weights are proportionally compressed
    to maintain Layer 3 total = 1.0.
    
    Args:
        base_weight: Base weight for UCS dimension (from UCS_BASE_WEIGHTS)
        ucs_score: Model's UCS score (0-3)
    
    Returns:
        Adjusted weight for UCS dimension
    """
    scaling = UCS_WEIGHT_SCALING.get(ucs_score, 1.0)
    return base_weight * scaling


def compute_layer3_with_ucs(
    dimension_scores: dict,
    dimension_weights: dict,
    ucs_score: int,
    uncertainty_type: str
) -> float:
    """
    Compute Layer 3 composite score with dynamic UCS weight scaling.
    
    When UCS weight increases, other dimensions' weights are 
    proportionally compressed to maintain total weight = 1.0.
    
    Args:
        dimension_scores: Dict of dimension_id → score (0-1)
        dimension_weights: Dict of dimension_id → base weight
        ucs_score: Model's UCS score (0-3)
        uncertainty_type: Question's uncertainty type
    
    Returns:
        Weighted composite Layer 3 score (0-1)
    """
    # Get adjusted UCS weight
    ucs_base = UCS_BASE_WEIGHTS.get(uncertainty_type, 0.10)
    ucs_adjusted = get_ucs_weight(ucs_base, ucs_score)
    
    # Compute total base weight
    total_base = sum(dimension_weights.values())
    
    # Compute weight adjustment
    ucs_diff = ucs_adjusted - ucs_base  # Extra weight for UCS
    other_total_base = total_base - ucs_base  # Base weight of non-UCS dimensions
    
    # Proportionally compress other dimensions
    compression_factor = (other_total_base - ucs_diff) / other_total_base if other_total_base > 0 else 1.0
    compression_factor = max(0.5, compression_factor)  # Don't compress more than 50%
    
    # Compute weighted score
    weighted_sum = 0.0
    total_weight = 0.0
    
    for dim_id, score in dimension_scores.items():
        if dim_id == "uncertainty_calibration":
            weight = ucs_adjusted
        else:
            weight = dimension_weights.get(dim_id, 0.0) * compression_factor
        
        weighted_sum += score * weight
        total_weight += weight
    
    return weighted_sum / total_weight if total_weight > 0 else 0.0


# ============================================================================
# Question Annotation Helpers
# ============================================================================

# Uncertainty type determination heuristics
UNCERTAINTY_TYPE_KEYWORDS = {
    "NO_DIFFERENCE": [
        "no significant difference", "no difference", "comparable",
        "similar outcomes", "equally effective", "volume equated"
    ],
    "MIXED_EVIDENCE": [
        "mixed evidence", "conflicting findings", "inconsistent results",
        "some studies show", "debate continues", "controversial"
    ],
    "INSUFFICIENT_EVIDENCE": [
        "insufficient evidence", "limited research", "few studies",
        "more research needed", "understudied", "evidence gap"
    ],
    "EVOLVING": [
        "guidelines have changed", "previously recommended",
        "updated recommendation", "evolution of", "shift from"
    ],
    "CONSENSUS": [
        "well-established", "consensus", "widely accepted",
        "position stand", "clear recommendation", "standard practice"
    ]
}


def suggest_uncertainty_type(ground_truth: str) -> str:
    """
    Suggest uncertainty_type based on ground truth text.
    This is a HELPER — final annotation should be human-verified.
    """
    gt_lower = ground_truth.lower()
    scores = {}
    
    for utype, keywords in UNCERTAINTY_TYPE_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in gt_lower)
        if score > 0:
            scores[utype] = score
    
    if scores:
        return max(scores, key=scores.get)
    return "CONSENSUS"  # Default for position stand-based questions


def suggest_evidence_level(sources: list) -> str:
    """
    Suggest evidence_level based on source descriptions.
    This is a HELPER — final annotation should be human-verified.
    """
    sources_text = " ".join(sources).lower()
    
    if any(kw in sources_text for kw in ["meta-analysis", "systematic review", "meta analysis"]):
        return "A"
    elif any(kw in sources_text for kw in ["position stand", "position statement", "guidelines"]):
        return "A"
    elif any(kw in sources_text for kw in ["rct", "randomized", "controlled trial"]):
        return "B"
    elif any(kw in sources_text for kw in ["observational", "cohort", "cross-sectional"]):
        return "C"
    else:
        return "B"  # Default for position stand citations


# ============================================================================
# Export / Summary
# ============================================================================

def get_ucs_summary(ucs_result: UCSResult) -> dict:
    """Generate a summary dict for reporting."""
    return {
        "ucs_score": ucs_result.ucs_score,
        "ucs_label": {
            0: "Overconfident",
            1: "Pseudo-precise",
            2: "Hedged",
            3: "Calibrated"
        }.get(ucs_result.ucs_score, "Unknown"),
        "ecs_score": ucs_result.ecs_score,
        "stage_used": ucs_result.stage_used,
        "needs_review": ucs_result.needs_manual_review,
        "review_reason": ucs_result.review_reason,
        "extraction_features": {
            "claims_superiority": ucs_result.extraction.claims_superiority if ucs_result.extraction else None,
            "has_directional_claim": ucs_result.extraction.has_directional_claim if ucs_result.extraction else None,
            "mentions_no_difference": ucs_result.extraction.mentions_no_difference if ucs_result.extraction else None,
            "has_hedging": ucs_result.extraction.has_hedging if ucs_result.extraction else None,
            "cites_evidence_type": ucs_result.extraction.cites_evidence_type if ucs_result.extraction else None,
        } if ucs_result.extraction else None
    }
