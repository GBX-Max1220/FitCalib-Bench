# FitRAG-Bench V2 评分函数定义

## Scoring Functions Definition V2

**Version**: 2.0  
**Based on**: FitRAG-Bench Three-Layer Evaluation Framework with Question-Type Adaptation  
**Last Updated**: 2026-05-06

---

## 1. 评分函数总览 / Overview

FitRAG-Bench V2 采用三层评分体系，支持按题目类型（FAC/SCE/ADV/BND/REC）动态调整规则集和权重：

| Layer | Scoring Function | Output Range | Default Weight | Weight Varies By Type |
|-------|-----------------|--------------|----------------|----------------------|
| Layer 1: Hard Constraints | `binary_pass_fail` | {0, 1} | 40% | Yes (30-50%) |
| Layer 2: Soft Constraints | `distance_based` | [0, 1] | 30% | Yes (5-30%) |
| Layer 3: Structured Semantic | `sub_check_ratio` | [0, 1] | 30% | Yes (30-60%) |

### Question Type Weight Summary

| Question Type | Layer1 Weight | Layer2 Weight | Layer3 Weight |
|--------------|---------------|---------------|---------------|
| FAC (Factual) | 0.35 | 0.30 | 0.35 |
| SCE (Scenario) | 0.40 | 0.30 | 0.30 |
| ADV (Adversarial) | 0.30 | 0.10 | 0.60 |
| BND (Boundary) | 0.50 | 0.05 | 0.45 |
| REC (Recency) | 0.30 | 0.20 | 0.50 |

---

## 2. N/A 规则处理 / N/A Rule Handling

### 核心原则
- **N/A 规则不计入分母**：当某规则对特定题目类型不适用时，从分母中排除
- **N/A 规则不计入分子**：N/A 不算作通过或失败

### 计算公式
```
applicable_rules = all_rules.filter(rule => rule.applicability[type] != "not_applicable")
layer_score = passed_among_applicable / count(applicable_rules)
```

### 示例
对于 BND-001（边界题）：
- Layer1: 4个 HYP 规则全部 N/A，只有 BND-HARD-001, BND-HARD-002, HYP-HARD-002 可用
- 实际评分: (passed_rules) / 3 (而非 / 5)

---

## 3. Layer 1: Binary Pass/Fail (Extended)

### 函数定义 / Function Definition

```python
def binary_pass_fail_v2(
    check_result: bool,
    rule_id: str,
    question_type: str,
    rule_profile: dict
) -> dict:
    """
    Layer 1: Hard Constraints Scoring V2
    
    Args:
        check_result: True if constraint is satisfied, False otherwise
        rule_id: The rule being evaluated
        question_type: FAC/SCE/ADV/BND/REC
        rule_profile: Rule profile from rule_profile.json
    
    Returns:
        Dict with score and applicability info
    """
    applicability = get_applicability(rule_id, question_type, rule_profile)
    
    if applicability == "not_applicable":
        return {
            "score": None,
            "result": "N/A",
            "applicability": "not_applicable",
            "reason": f"Rule {rule_id} is not applicable for question type {question_type}"
        }
    
    # Conditional rules: evaluate only if condition is met
    if applicability == "conditional":
        condition_met = evaluate_condition(rule_id, question_context)
        if not condition_met:
            return {
                "score": None,
                "result": "N/A",
                "applicability": "conditional_skipped",
                "reason": f"Condition for {rule_id} not met in this context"
            }
    
    return {
        "score": 1.0 if check_result else 0.0,
        "result": "PASS" if check_result else "FAIL",
        "applicability": "applicable"
    }
```

### N/A 规则排除示例

| Question | Rule | V1 Result | V2 Result | Reason |
|----------|------|-----------|-----------|--------|
| ADV-001 | HYP-HARD-001 (frequency) | FAIL | N/A | 辟谣题不涉及训练频率建议 |
| BND-001 | HYP-HARD-001 (frequency) | N/A | N/A | 边界题不涉及训练频率 |
| BND-001 | BND-HARD-001 (scope) | N/A | EVALUATED | 新增边界规则，现在有实际评分 |

---

## 4. Layer 2: Distance-Based Scoring (Extended)

### 函数定义 / Function Definition

```python
def distance_based_score_v2(
    value: float,
    rule_id: str,
    question_type: str,
    rule_config: dict
) -> dict:
    """
    Layer 2: Soft Constraints Scoring V2
    
    Handles N/A rules by excluding them from scoring.
    """
    applicability = rule_config.get("applicability", {}).get(question_type)
    
    if applicability in ["not_applicable", None]:
        return {
            "score": None,
            "result": "N/A",
            "reason": f"Rule {rule_id} not applicable for {question_type}"
        }
    
    if applicability == "conditional":
        if not condition_met:
            return {
                "score": None,
                "result": "N/A",
                "reason": "Condition not met"
            }
    
    # Standard distance-based scoring
    score = calculate_distance_score(value, rule_config)
    
    return {
        "score": score,
        "result": "SCORED"
    }
```

### Special Scoring for ADV/REC Questions

For ADV-SOFT-001 (myth identification) and REC-SOFT-001 (temporal accuracy):

```python
def rubric_based_score(
    response: str,
    rubric: dict,
    rule_id: str
) -> float:
    """
    Rubric-based scoring for qualitative assessments.
    Used for adversarial reasoning and temporal awareness dimensions.
    """
    # Check for presence of keywords from different score levels
    scores = []
    
    for level in [1.0, 0.75, 0.5, 0.25, 0.0]:
        keywords = rubric[str(level)].split()
        if any(kw in response.lower() for kw in keywords):
            return level
    
    return 0.0  # Default to lowest if no match
```

---

## 5. Layer 3: Sub-Check Ratio (Extended)

### 函数定义 / Function Definition

```python
def sub_check_ratio_v2(
    response: str,
    dimensions: list,
    question_type: str,
    dimension_weights: dict
) -> dict:
    """
    Layer 3: Structured Semantic Scoring V2
    
    Args:
        response: The response text to evaluate
        dimensions: List of dimension definitions
        question_type: FAC/SCE/ADV/BND/REC
        dimension_weights: Weight configuration from rule_profile.json
    
    Returns:
        Dict with weighted dimension scores and composite score
    """
    dimension_scores = []
    
    for dimension in dimensions:
        # Check applicability
        applicability = dimension.get("applicability", {}).get(question_type, "not_applicable")
        
        if applicability == "not_applicable":
            continue  # Skip this dimension
        
        if applicability == "conditional":
            if not evaluate_condition(dimension["rule_id"], context):
                continue
        
        # Evaluate sub-checks
        results = []
        for sub_check in dimension["sub_checks"]:
            passed = evaluate_sub_check(response, sub_check)
            results.append({
                "check_id": sub_check["check_id"],
                "passed": passed
            })
        
        dimension_score = sum(1 for r in results if r["passed"]) / len(results)
        
        dimension_scores.append({
            "dimension_id": dimension["rule_id"],
            "score": dimension_score,
            "weight": dimension_weights.get(dimension["rule_id"], 0)
        })
    
    # Calculate weighted composite
    total_weight = sum(d["weight"] for d in dimension_scores)
    weighted_score = sum(d["score"] * d["weight"] for d in dimension_scores) / total_weight
    
    return {
        "dimension_scores": dimension_scores,
        "composite_score": weighted_score,
        "total_dimensions_evaluated": len(dimension_scores)
    }
```

### New Dimensions for V2

#### ADV-SEM-001: Adversarial Reasoning
Weighs heavily for ADV questions (30% of Layer3):
- Myth identification
- Evidence provision
- Historical context
- Nuance acknowledgment

#### BND-SEM-001: Scope Awareness
Weighs heavily for BND questions (20% of Layer3):
- Professional boundary recognition
- Medical referral recommendation
- Scope limitation acknowledgment
- Healthcare pathway guidance

#### REC-SEM-001: Temporal Awareness
Weighs heavily for REC questions (20% of Layer3):
- Version/citation accuracy
- Timeline distinction
- Change explanation
- Future evolution acknowledgment

---

## 6. Composite Score Calculation

### V2 Composite Formula

```python
def calculate_composite_score_v2(
    layer1_result: dict,
    layer2_result: dict,
    layer3_result: dict,
    question_type: str,
    weights: dict
) -> dict:
    """
    Calculate composite score with type-specific weights.
    
    N/A rules are excluded from both numerator and denominator.
    """
    # Get weights for question type
    type_weights = weights[question_type]
    
    # Layer 1: Count applicable rules only
    l1_applicable = [r for r in layer1_result["rules"] if r["result"] != "N/A"]
    l1_score = sum(r["score"] for r in l1_applicable) / len(l1_applicable) if l1_applicable else 1.0
    
    # Layer 2: Count applicable rules only
    l2_applicable = [r for r in layer2_result["rules"] if r["result"] != "N/A"]
    l2_score = sum(r["score"] for r in l2_applicable) / len(l2_applicable) if l2_applicable else 1.0
    
    # Layer 3: Already weighted by dimension_weights_by_type
    l3_score = layer3_result["composite_score"]
    
    # Composite
    composite = (
        type_weights["layer1"] * l1_score +
        type_weights["layer2"] * l2_score +
        type_weights["layer3"] * l3_score
    )
    
    return {
        "composite_score": composite,
        "layer1_score": l1_score,
        "layer2_score": l2_score,
        "layer3_score": l3_score,
        "weights_used": type_weights,
        "na_statistics": {
            "layer1_na_count": len(layer1_result["rules"]) - len(l1_applicable),
            "layer2_na_count": len(layer2_result["rules"]) - len(l2_applicable),
            "layer3_na_count": 8 - layer3_result["total_dimensions_evaluated"]
        }
    }
```

### Weight Application Examples

**ADV-001 (辟谣题)**: 
- Layer1: 30% (safety_critical + myth_identification rules)
- Layer2: 10% (myth_identification accuracy only)
- Layer3: 60% (adversarial_reasoning gets 30% weight)

**BND-001 (边界题)**:
- Layer1: 50% (safety escalation rules critical)
- Layer2: 5% (minimal prescription focus)
- Layer3: 45% (safety_awareness 35% + scope_awareness 20%)

**REC-001 (时效题)**:
- Layer1: 30% (no outdated as current)
- Layer2: 20% (temporal accuracy)
- Layer3: 50% (source_grounding 35% + temporal_awareness 20%)

---

## 7. N/A Rate Reduction Evidence

### V1 vs V2 N/A Comparison

| Question | Type | V1 N/A Rate | V2 N/A Rate | Improvement |
|----------|------|-------------|-------------|-------------|
| FAC-001 | FAC | 60% (Layer1) | 0% | All rules relevant |
| ADV-001 | ADV | 80% (Layer1) | 50% | Irrelevant HYP rules excluded |
| BND-001 | BND | 80% (Layer1) | 0% | New boundary rules added |

### Expected N/A Rate Reduction

- **FAC questions**: ~40% → ~10% (irrelevant prescription rules now conditional)
- **ADV questions**: ~75% → ~20% (myth-specific rules replace generic rules)
- **BND questions**: ~80% → ~10% (new scope rules provide actual evaluation)
- **REC questions**: ~70% → ~15% (temporal rules provide evaluation basis)

---

## 8. Scoring Examples

### Example 1: ADV-001 (V2 Evaluation)

**Question**: "膝盖不超过脚尖辟谣"
**Response**: [DeepSeek's debunking response]

**Layer 1 V2**:
- HYP-HARD-002 (safety): PASS
- HYP-HARD-001 (frequency): N/A
- HYP-HARD-003 (progression): N/A
- ADV-HARD-001 (no myth as fact): PASS
- ADV-HARD-002 (evidence provided): PASS
- Score: 3/3 = 1.0

**Layer 2 V2**:
- All HYP-SOFT rules: N/A
- ADV-SOFT-001 (myth identification): Score 0.75
- Score: 0.75

**Layer 3 V2**:
- adversarial_reasoning: 0.875 (4/4 checks)
- source_grounding: 0.5
- contextual_nuance: 0.75
- Score: Weighted = 0.825

**Composite** (ADV weights: L1=0.30, L2=0.10, L3=0.60):
= 0.30 * 1.0 + 0.10 * 0.75 + 0.60 * 0.825 = 0.30 + 0.075 + 0.495 = **0.87**

### Example 2: BND-001 (V2 Evaluation)

**Question**: "客户胸痛处理"
**Response**: [DeepSeek's safety response]

**Layer 1 V2**:
- HYP-HARD-002 (safety cessation): PASS
- BND-HARD-001 (scope recognition): PASS
- BND-HARD-002 (medical referral): PASS
- HYP-HARD-001/003/004/005: N/A
- Score: 3/3 = 1.0

**Layer 2 V2**:
- All rules: N/A
- Score: 1.0 (no applicable rules)

**Layer 3 V2**:
- safety_awareness: 1.0 (4/4)
- scope_awareness: 1.0 (4/4)
- contextual_nuance: 0.75
- Score: Weighted = 0.95

**Composite** (BND weights: L1=0.50, L2=0.05, L3=0.45):
= 0.50 * 1.0 + 0.05 * 1.0 + 0.45 * 0.95 = 0.50 + 0.05 + 0.428 = **0.978**

---

## 9. Implementation Notes

### File Requirements
1. `rule_profile.json` - Central configuration for rule applicability
2. `layer1_hard_extended.json` - Extended hard rules with applicability
3. `layer2_soft_extended.json` - Extended soft rules with applicability
4. `layer3_semantic_extended.json` - Extended dimensions with applicability

### Scoring Pipeline
```python
def evaluate_response_v2(
    question_id: str,
    question_type: str,
    response: str,
    config: RuleConfig
) -> EvaluationResult:
    # 1. Load applicable rules for question type
    rules = load_applicable_rules(question_type, config)
    
    # 2. Evaluate Layer 1
    layer1 = evaluate_layer1(response, rules["layer1"])
    
    # 3. Evaluate Layer 2
    layer2 = evaluate_layer2(response, rules["layer2"])
    
    # 4. Evaluate Layer 3
    layer3 = evaluate_layer3(response, rules["layer3"], 
                           config.dimension_weights[question_type])
    
    # 5. Calculate composite
    composite = calculate_composite_score_v2(
        layer1, layer2, layer3,
        question_type,
        config.weights
    )
    
    return EvaluationResult(composite=composite, details={...})
```

### Conditional Rule Evaluation
Rules marked as "conditional" are evaluated based on question context:
- FAC: HYP-HARD-001 only if question mentions frequency
- ADV: REC-HARD-001 only if question references guidelines

---

## 10. Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-05-06 | Initial version with HYP-only rules |
| 2.0 | 2026-05-06 | Added question-type adaptation, N/A handling, new rules |
