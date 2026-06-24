# FitRAG-Bench V2 Evaluation Protocol

## Evaluation Protocol V2 - Question Type Adaptive Evaluation

**Version**: 2.0  
**Last Updated**: 2026-05-06  
**Based on**: FitRAG-Bench Three-Layer Framework with Conditional Adaptation

---

## 1. Overview

FitRAG-Bench V2 introduces a **question-type adaptive evaluation system** that:

1. **Matches rules to question types**: Different question types (FAC/SCE/ADV/BND/REC) use different rule sets
2. **Reduces N/A rates**: Irrelevant rules are excluded from scoring
3. **Adds new dimensions**: Type-specific rules like adversarial reasoning, scope awareness, temporal awareness
4. **Adjusts weights**: Critical dimensions receive higher weights per question type

### Core Problem Addressed

V1 Problem:
- ADV-001 (膝盖不过脚尖辟谣) scored on training frequency rules → FAIL
- BND-001 (胸痛处理) scored on hypertrophy volume rules → N/A
- N/A rates of 60-80% on non-scenario questions

V2 Solution:
- ADV questions evaluated on myth identification and evidence quality
- BND questions evaluated on scope awareness and safety escalation
- New rules provide actual evaluation basis

---

## 2. Question Type Definitions

### 2.1 Factual (FAC)
**Focus**: Knowledge accuracy and source grounding

| Aspect | Description |
|--------|-------------|
| Purpose | Test factual accuracy of exercise science knowledge |
| Count | 10 questions |
| Key Rules | FAC-HARD-001, FAC-HARD-002, HYP-HARD-002 |
| Key Dimensions | source_grounding (30%), safety_awareness (20%) |
| Weights | L1=35%, L2=30%, L3=35% |

**Example**: FAC-001 "Valsalva动作安全性建议"

### 2.2 Scenario (SCE)
**Focus**: Prescription capability and safety

| Aspect | Description |
|--------|-------------|
| Purpose | Test practical prescription and client management |
| Count | 8 questions |
| Key Rules | All HYP-HARD rules, all HYP-SOFT rules |
| Key Dimensions | individualization (25%), safety_awareness (25%) |
| Weights | L1=40%, L2=30%, L3=30% |

**Example**: SCE-001 "高血压患者硬拉指导"

### 2.3 Adversarial (ADV)
**Focus**: Myth identification and evidence-based rebuttal

| Aspect | Description |
|--------|-------------|
| Purpose | Test ability to debunk fitness myths with evidence |
| Count | 5 questions |
| Key Rules | ADV-HARD-001, ADV-HARD-002, ADV-SOFT-001 |
| Key Dimensions | adversarial_reasoning (30%), contextual_nuance (20%) |
| Weights | L1=30%, L2=10%, L3=60% |

**Example**: ADV-001 "膝盖不超过脚尖辟谣"

### 2.4 Boundary (BND)
**Focus**: Professional scope and safety escalation

| Aspect | Description |
|--------|-------------|
| Purpose | Test recognition of professional boundaries and medical referral |
| Count | 3 questions |
| Key Rules | BND-HARD-001, BND-HARD-002, HYP-HARD-002 |
| Key Dimensions | safety_awareness (35%), scope_awareness (20%) |
| Weights | L1=50%, L2=5%, L3=45% |

**Example**: BND-001 "客户胸痛处理"

### 2.5 Recency (REC)
**Focus**: Temporal knowledge and guideline evolution

| Aspect | Description |
|--------|-------------|
| Purpose | Test understanding of guideline changes over time |
| Count | 2 questions |
| Key Rules | REC-HARD-001, REC-HARD-002, REC-SOFT-001 |
| Key Dimensions | source_grounding (35%), temporal_awareness (20%) |
| Weights | L1=30%, L2=20%, L3=50% |

**Example**: REC-001 "增肌次数区间建议演变"

---

## 3. Evaluation Workflow

### Step 1: Question Classification
```python
def classify_question(question_id: str) -> str:
    """
    Determine question type from question ID prefix.
    
    FAC-* → FAC
    SCE-* → SCE
    ADV-* → ADV
    BND-* → BND
    REC-* → REC
    """
    prefix = question_id.split("-")[0]
    return prefix  # FAC, SCE, ADV, BND, or REC
```

### Step 2: Load Applicable Rules
```python
def load_applicable_rules(question_type: str, config: RuleConfig) -> dict:
    """
    Load rules applicable to specific question type.
    
    - Excludes rules marked 'not_applicable'
    - Identifies 'conditional' rules for context evaluation
    """
    rules = {
        "layer1": [],
        "layer2": [],
        "layer3": []
    }
    
    for rule in config.layer1_extended:
        applicability = rule["applicability"].get(question_type)
        if applicability != "not_applicable":
            rules["layer1"].append({
                "rule": rule,
                "applicability": applicability
            })
    
    # Same for layer2 and layer3
    return rules
```

### Step 3: Evaluate Layer 1
```python
def evaluate_layer1_v2(
    response: str,
    rules: list,
    question_context: dict
) -> Layer1Result:
    """
    Evaluate Layer 1 with N/A handling.
    
    - Skip 'not_applicable' rules
    - Evaluate 'conditional' rules only if context matches
    - Score 'applicable' rules as binary pass/fail
    """
    results = []
    
    for rule_entry in rules:
        rule = rule_entry["rule"]
        applicability = rule_entry["applicability"]
        
        if applicability == "not_applicable":
            continue  # Skip
        
        if applicability == "conditional":
            if not matches_condition(rule["condition"], question_context):
                continue  # Skip conditional if not met
        
        # Evaluate the rule
        passed = evaluate_binary_rule(response, rule)
        results.append({
            "rule_id": rule["rule_id"],
            "passed": passed,
            "score": 1.0 if passed else 0.0
        })
    
    score = sum(r["score"] for r in results) / len(results) if results else 1.0
    
    return {
        "score": score,
        "results": results,
        "applicable_count": len(results),
        "na_count": len(rules) - len(results)
    }
```

### Step 4: Evaluate Layer 2
```python
def evaluate_layer2_v2(
    response: str,
    rules: list,
    question_context: dict
) -> Layer2Result:
    """
    Evaluate Layer 2 with distance-based scoring.
    
    - Handle N/A rules
    - Apply distance-based or rubric-based scoring
    - Return N/A statistics
    """
    results = []
    
    for rule_entry in rules:
        rule = rule_entry["rule"]
        applicability = rule_entry["applicability"]
        
        if applicability == "not_applicable":
            continue
        
        if applicability == "conditional":
            if not matches_condition(rule.get("condition"), question_context):
                continue
        
        # Extract numeric value if present, or use rubric
        if rule.get("scoring_method") == "rubric_based":
            score = rubric_based_score(response, rule["scoring_rubric"])
        else:
            value = extract_numeric_value(response, rule)
            score = distance_based_score(value, rule)
        
        results.append({
            "rule_id": rule["rule_id"],
            "score": score,
            "value": value if rule.get("scoring_method") != "rubric_based" else "N/A"
        })
    
    score = sum(r["score"] for r in results) / len(results) if results else 1.0
    
    return {
        "score": score,
        "results": results,
        "applicable_count": len(results),
        "na_count": len(rules) - len(results)
    }
```

### Step 5: Evaluate Layer 3
```python
def evaluate_layer3_v2(
    response: str,
    dimensions: list,
    dimension_weights: dict,
    question_type: str
) -> Layer3Result:
    """
    Evaluate Layer 3 with weighted dimensions.
    
    - Evaluate applicable dimensions only
    - Weight dimensions by question type
    - Calculate composite dimension score
    """
    dimension_scores = []
    
    for dim in dimensions:
        applicability = dim.get("applicability", {}).get(question_type, "not_applicable")
        
        if applicability == "not_applicable":
            continue
        
        # Evaluate sub-checks
        passed = 0
        total = len(dim["sub_checks"])
        
        for sub_check in dim["sub_checks"]:
            if evaluate_sub_check(response, sub_check):
                passed += 1
        
        dimension_score = passed / total if total > 0 else 0
        weight = dimension_weights.get(dim["rule_id"], 0)
        
        dimension_scores.append({
            "dimension_id": dim["rule_id"],
            "score": dimension_score,
            "weight": weight,
            "passed": passed,
            "total": total
        })
    
    # Calculate weighted composite
    total_weight = sum(d["weight"] for d in dimension_scores)
    composite = (
        sum(d["score"] * d["weight"] for d in dimension_scores) / total_weight
        if total_weight > 0 else 0
    )
    
    return {
        "score": composite,
        "dimension_scores": dimension_scores,
        "total_dimensions_evaluated": len(dimension_scores),
        "na_dimensions": 8 - len(dimension_scores)  # 8 total in extended set
    }
```

### Step 6: Calculate Composite Score
```python
def calculate_composite_v2(
    layer1: Layer1Result,
    layer2: Layer2Result,
    layer3: Layer3Result,
    question_type: str,
    weights: dict
) -> CompositeResult:
    """
    Calculate final composite score with type-specific weights.
    """
    type_weights = weights[question_type]
    
    composite = (
        type_weights["layer1"] * layer1["score"] +
        type_weights["layer2"] * layer2["score"] +
        type_weights["layer3"] * layer3["score"]
    )
    
    return {
        "composite_score": composite,
        "layer1_score": layer1["score"],
        "layer2_score": layer2["score"],
        "layer3_score": layer3["score"],
        "weights_used": type_weights,
        "na_statistics": {
            "layer1_na": layer1["na_count"],
            "layer2_na": layer2["na_count"],
            "layer3_na": layer3["na_dimensions"]
        }
    }
```

---

## 4. Uncertainty Calibration

### 4.1 Overview

The **Uncertainty Calibration Score (UCS)** evaluates whether a model's response correctly expresses the epistemic state of the evidence using a **sequential decision tree** (not a holistic rubric).

Key design decisions:
1. **Decision tree** over descriptive rubric: Clear if-then rules produce ≥85% inter-rater agreement
2. **Dynamic weight scaling** over penalty multiplier: UCS dimension weight increases when model is overconfident, without penalizing other Layer 3 dimensions
3. **ECS (Evidence Citation Signal)**: Binary field for analysis, not scoring

### 4.2 UCS Evaluation Flow

```
Evaluate Layer 1 → Layer 2 → Layer 3 (as normal)
                                      ↓
                        Evaluate UCS via Decision Tree (0-3)
                                      ↓
                    Evaluate ECS (Evidence Citation Signal)
                                      ↓
                    Compute dynamic UCS weight for Layer 3
                                      ↓
                    Calculate final composite score
```

### 4.3 UCS Decision Tree

The decision tree has **4 steps evaluated sequentially**. The first matching step determines the UCS score.

```
STEP 1: Explicit superiority claim when evidence shows none?
  → "X is superior/better/more effective than Y" when no sig diff exists
  → "The best approach is X" on controversial topics
  → UCS = 0 (OVERCONFIDENT) — STOP

STEP 2: Explicit evidence state stated?
  → "no significant difference" / "meta-analyses show no difference"
  → "evidence is mixed/inconclusive"
  → "insufficient evidence to determine superiority"
  → UCS = 3 (CALIBRATED) — STOP

STEP 3: Vague hedging only (no directional claim)?
  → "It depends on the individual"
  → "Could go either way"
  → "More research is needed" (vague)
  → UCS = 2 (HEDGED) — STOP

STEP 4: Hedging + directional claim combined?
  → "Depends, but DUP tends to be better"
  → "Both work, though A has a slight edge"
  → UCS = 1 (PSEUDO-PRECISE)
```

### 4.4 UCS Evaluation Code

```python
def evaluate_ucs(
    response: str,
    question: QuestionMetadata
) -> UCSResult:
    """
    Evaluate UCS via sequential decision tree.
    
    Returns:
    - ucs_score: 0-3
    - ucs_method: "decision_tree" | "llm_judge_fallback"
    - justification: Why this score was assigned
    - step_triggered: Which step of the decision tree triggered
    """
    uncertainty_type = question.get("uncertainty_type", "CONSENSUS")
    evidence_level = question.get("evidence_level", "B")
    ucs_rubric_note = question.get("ucs_rubric_note", "")
    
    # Apply decision tree
    step1 = check_superiority_claim(response, uncertainty_type, ucs_rubric_note)
    if step1.triggered:
        return UCSResult(
            score=0,
            method="decision_tree",
            step_triggered=1,
            justification=step1.justification,
            ucs_score_display="0 — Overconfident",
            pattern_matched=step1.pattern
        )
    
    step2 = check_explicit_evidence_state(response, uncertainty_type, ucs_rubric_note)
    if step2.triggered:
        return UCSResult(
            score=3,
            method="decision_tree",
            step_triggered=2,
            justification=step2.justification,
            ucs_score_display="3 — Calibrated",
            pattern_matched=step2.pattern
        )
    
    step3 = check_vague_hedging_only(response, ucs_rubric_note)
    if step3.triggered:
        return UCSResult(
            score=2,
            method="decision_tree",
            step_triggered=3,
            justification=step3.justification,
            ucs_score_display="2 — Hedged",
            pattern_matched=step3.pattern
        )
    
    step4 = check_hedging_plus_direction(response, ucs_rubric_note)
    if step4.triggered:
        return UCSResult(
            score=1,
            method="decision_tree",
            step_triggered=4,
            justification=step4.justification,
            ucs_score_display="1 — Pseudo-precise",
            pattern_matched=step4.pattern
        )
    
    # Fallback: LLM-as-judge for truly ambiguous cases
    llm_result = llm_judge_ucs(
        response=response,
        question=question["question"],
        ground_truth=question["ground_truth"],
        uncertainty_type=uncertainty_type,
        evidence_level=evidence_level,
        rubric_note=ucs_rubric_note
    )
    
    return UCSResult(
        score=llm_result.score,
        method="llm_judge_fallback",
        step_triggered=None,
        justification=llm_result.justification,
        llm_confidence=llm_result.confidence
    )
```

### 4.5 ECS Evaluation

```python
def evaluate_ecs(response: str, ecs_expected: bool) -> ECSResult:
    """
    Evaluate Evidence Citation Signal.
    
    ECS = 1: Response mentions evidence TYPE (meta-analysis, RCT, position stand, etc.)
    ECS = 0: Response states conclusions without referencing evidence type
    
    ECS does NOT affect the main score. It is an analysis field.
    """
    evidence_type_patterns = [
        r"\bmeta-analysis\b", r"\bsystematic review\b",
        r"\bRCT\b", r"\brandomi", r"\bcohort\b",
        r"\bposition stand\b", r"\bposition statement\b",
        r"\bconsensus\b", r"\bguidelines\b",
        r"\bsystematic review and meta-analysis\b"
    ]
    
    for pattern in evidence_type_patterns:
        if re.search(pattern, response, re.IGNORECASE):
            return ECSResult(score=1, matched_pattern=pattern)
    
    return ECSResult(score=0, matched_pattern=None)
```

### 4.6 Dynamic Weight Scaling

```python
def get_ucs_weight(base_weight: float, ucs_score: int) -> float:
    """
    UCS weight scales up when model is overconfident (low UCS score).
    This amplifies the epistemic penalty within Layer3 without contaminating other dimensions.
    
    Scaling:
    - UCS=0 (Overconfident): weight × 1.6
    - UCS=1 (Pseudo-precise): weight × 1.2
    - UCS=2 (Hedged): weight × 1.0
    - UCS=3 (Calibrated): weight × 1.0
    """
    scaling = {0: 1.6, 1: 1.2, 2: 1.0, 3: 1.0}
    return base_weight * scaling.get(ucs_score, 1.0)


BASE_UCS_WEIGHTS = {
    "NO_DIFFERENCE": 0.25,
    "MIXED_EVIDENCE": 0.20,
    "INSUFFICIENT_EVIDENCE": 0.15,
    "CONSENSUS": 0.05,
    "EVOLVING": 0.10
}


def calculate_layer3_with_ucs(
    other_dimensions_score: float,  # Score from 8 other Layer 3 dimensions (0-1)
    ucs_score: int,                  # 0-3 from decision tree
    uncertainty_type: str,
    num_other_dimensions: int = 8
) -> float:
    """
    Compute Layer 3 composite with dynamic UCS weight scaling.
    
    UCS is one of 9 sub-dimensions in Layer 3.
    The 8 other dimensions share (1 - effective_ucs_weight).
    UCS contributes (ucs_score/3) × effective_ucs_weight.
    """
    base_weight = BASE_UCS_WEIGHTS.get(uncertainty_type, 0.10)
    effective_ucs_weight = get_ucs_weight(base_weight, ucs_score)
    
    # UCS contribution: score on 0-1 scale × effective weight
    ucs_normalized = ucs_score / 3.0
    ucs_contribution = ucs_normalized * effective_ucs_weight
    
    # Other dimensions: maintain their score, share remaining weight
    other_weight = 1.0 - effective_ucs_weight
    other_contribution = other_dimensions_score * other_weight
    
    return ucs_contribution + other_contribution
```

**Example calculation for NO_DIFFERENCE question:**
```
Base UCS weight: 25%
Other dimensions score: 0.80

UCS=0 (Overconfident):
  Effective UCS weight: 25% × 1.6 = 40%
  UCS contribution: (0/3) × 0.40 = 0.00
  Other contribution: 0.80 × (1-0.40) = 0.80 × 0.60 = 0.48
  L3 with UCS: 0.00 + 0.48 = 0.48

UCS=3 (Calibrated):
  Effective UCS weight: 25% × 1.0 = 25%
  UCS contribution: (3/3) × 0.25 = 1.00 × 0.25 = 0.25
  Other contribution: 0.80 × 0.75 = 0.60
  L3 with UCS: 0.25 + 0.60 = 0.85

UCS=2 (Hedged):
  Effective UCS weight: 25% × 1.0 = 25%
  UCS contribution: (2/3) × 0.25 = 0.667 × 0.25 = 0.167
  Other contribution: 0.80 × 0.75 = 0.60
  L3 with UCS: 0.167 + 0.60 = 0.767
```

### 4.7 Final Composite Score

```python
def calculate_final_composite_with_ucs(
    layer1: Layer1Result,
    layer2: Layer2Result,
    other_dimensions_score: float,  # Layer 3 score from 8 other dimensions
    ucs_result: UCSResult,
    uncertainty_type: str,
    question_type: str,
    weights: dict
) -> FinalResult:
    """
    Calculate final composite score.
    
    L3 = calculate_layer3_with_ucs(other_dimensions_score, ucs_result.score, uncertainty_type)
    final = L1_weight * L1 + L2_weight * L2 + L3_weight * L3
    """
    l3_with_ucs = calculate_layer3_with_ucs(
        other_dimensions_score=other_dimensions_score,
        ucs_score=ucs_result.score,
        uncertainty_type=uncertainty_type
    )
    
    type_weights = weights[question_type]
    composite = (
        type_weights["layer1"] * layer1["score"] +
        type_weights["layer2"] * layer2["score"] +
        type_weights["layer3"] * l3_with_ucs
    )
    
    return FinalResult(
        composite_score=composite,
        layer1_score=layer1["score"],
        layer2_score=layer2["score"],
        layer3_other_dimensions=other_dimensions_score,
        layer3_with_ucs=l3_with_ucs,
        ucs_score=ucs_result.score,
        ucs_method=ucs_result.method,
        ucs_step=ucs_result.step_triggered,
        ucs_weight_used=get_ucs_weight(
            BASE_UCS_WEIGHTS.get(uncertainty_type, 0.10),
            ucs_result.score
        ),
        weights_used=type_weights
    )
```

### 4.8 ECS Integration

ECS does **not** participate in scoring. It is recorded separately:

```python
def add_ecs_to_result(result: FinalResult, ecs_result: ECSResult) -> FinalResult:
    result.ecs_score = ecs_result.score
    result.ecs_matched_pattern = ecs_result.matched_pattern
    result.ecs_note = "ECS is an analysis field only — not part of composite score"
    return result
```

ECS usage:
- **Tie-breaking**: When two models have the same UCS score, ECS=1 ranks higher
- **Research logging**: Recorded in all evaluation reports
- **Model behavior analysis**: Used to understand citation patterns

### 4.9 Backward Compatibility

Questions **without** UCS fields default to:

```python
UCS_DEFAULTS = {
    "uncertainty_type": "CONSENSUS",  # Default: low UCS weight (5%)
    "evidence_level": "B",
    "ecs_expected": False,
    "ucs_rubric_note": ""  # Empty — use decision tree without question-specific guidance
}

# With CONSENSUS defaults:
# - Base UCS weight = 5% (low)
# - Even if UCS=0, effective weight = 5% × 1.6 = 8%
# - Impact on composite score is minimal for legacy questions
```

---

## 5. Evaluation Example

### Example: ADV-001 (膝盖不过脚尖辟谣)

#### Step 1: Classify
- Question ID: ADV-001
- Type: **ADV**

#### Step 2: Load Applicable Rules
**Layer 1**:
| Rule | Applicability |
|------|---------------|
| HYP-HARD-002 | applicable |
| HYP-HARD-001 | not_applicable |
| HYP-HARD-003 | not_applicable |
| HYP-HARD-004 | not_applicable |
| HYP-HARD-005 | not_applicable |
| ADV-HARD-001 | applicable |
| ADV-HARD-002 | applicable |

**Layer 2**:
| Rule | Applicability |
|------|---------------|
| ADV-SOFT-001 | applicable |
| All HYP-SOFT | not_applicable |

**Layer 3**:
| Dimension | Weight | Applicable |
|-----------|--------|------------|
| individualization | 0.10 | yes |
| safety_awareness | 0.10 | yes |
| contextual_nuance | 0.20 | yes |
| source_grounding | 0.20 | yes |
| practical_actionability | 0.10 | yes |
| adversarial_reasoning | 0.30 | yes |

#### Step 3-5: Evaluate
```python
# Layer 1: 3/3 PASS = 1.0
# Layer 2: ADV-SOFT-001 score = 0.75
# Layer 3: Weighted dimensions = 0.825
```

#### Step 6: Composite
```
ADV weights: L1=0.30, L2=0.10, L3=0.60

composite = 0.30 * 1.0 + 0.10 * 0.75 + 0.60 * 0.825
          = 0.30 + 0.075 + 0.495
          = 0.87
```

---

## 6. File Structure

```
./FitRAG-Bench/rules/
├── rule_profile.json              # Central config: applicability matrix, weights
├── layer1_hard_extended.json      # Extended hard rules (16 total)
├── layer2_soft_extended.json      # Extended soft rules (7 total)
├── layer3_semantic_extended.json  # Extended dimensions (8 total)
├── scoring_functions.md           # V2 scoring functions
├── evaluation_protocol_v2.md      # This document
├── ucs_design.md                  # Uncertainty Calibration Score design
├── schema.md                      # Rule schema definition
├── layer1_hard.json               # Original HYP rules (legacy)
├── layer2_soft.json               # Original HYP rules (legacy)
└── layer3_semantic.json          # Original HYP dimensions (legacy)
```

---

## 7. Validation Checklist

### N/A Rate Reduction
- [ ] FAC questions: N/A rate < 15%
- [ ] ADV questions: N/A rate < 25%
- [ ] BND questions: N/A rate < 15%
- [ ] REC questions: N/A rate < 20%

### New Dimension Coverage
- [ ] ADV-SEM-001 (adversarial_reasoning) has 4 binary sub-checks
- [ ] BND-SEM-001 (scope_awareness) has 4 binary sub-checks
- [ ] REC-SEM-001 (temporal_awareness) has 4 binary sub-checks

### Weight Distribution
- [ ] BND: Layer1 weight = 50% (highest safety priority)
- [ ] ADV: Layer3 weight = 60% (highest reasoning priority)
- [ ] REC: Layer3 weight = 50%, source_grounding weight = 35%

### Score Validity
- [ ] All scores in [0, 1] range
- [ ] N/A rules excluded from denominator
- [ ] Conditional rules properly skipped when conditions unmet

---

## 8. Migration Guide

### From V1 to V2

**V1 Evaluation**:
```python
rules = load_all_rules()
results = evaluate_all(response, rules)
score = sum(results) / len(results)
```

**V2 Evaluation**:
```python
question_type = classify_question(question_id)
rules = load_applicable_rules(question_type, config)
results = evaluate_with_na_handling(response, rules)
score = calculate_composite_v2(results, question_type, weights)
```

**Key Changes**:
1. Add question classification step
2. Load rules based on question type
3. Handle N/A rules (exclude from denominator)
4. Apply type-specific weights to composite

---

## 9. Appendix: Applicability Matrix Summary

| Rule/Dimension | FAC | SCE | ADV | BND | REC |
|----------------|-----|-----|-----|-----|-----|
| HYP-HARD-001 | C | Y | N | N | N |
| HYP-HARD-002 | Y | Y | Y | Y | Y |
| HYP-HARD-003 | C | Y | N | N | N |
| HYP-HARD-004 | C | Y | N | N | N |
| HYP-HARD-005 | C | Y | N | N | N |
| FAC-HARD-001 | Y | Y | Y | Y | Y |
| FAC-HARD-002 | Y | C | C | N | Y |
| ADV-HARD-001 | C | C | Y | N | C |
| ADV-HARD-002 | N | N | Y | N | C |
| BND-HARD-001 | C | C | N | Y | N |
| BND-HARD-002 | C | C | N | Y | N |
| REC-HARD-001 | C | C | C | C | Y |
| REC-HARD-002 | N | N | N | N | Y |
| HYP-SEM-001 | Y | Y | Y | Y | Y |
| HYP-SEM-002 | Y | Y | Y | Y | Y |
| HYP-SEM-003 | Y | Y | Y | Y | Y |
| HYP-SEM-004 | Y | Y | Y | Y | Y |
| HYP-SEM-005 | Y | Y | Y | Y | Y |
| ADV-SEM-001 | C | C | Y | C | C |
| BND-SEM-001 | C | C | C | Y | C |
| REC-SEM-001 | C | C | C | C | Y |

Legend:
- Y = Applicable
- N = Not Applicable
- C = Conditional (evaluated only when context matches)
