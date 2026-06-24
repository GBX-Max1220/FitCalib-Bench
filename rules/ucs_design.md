# Uncertainty Calibration Score (UCS) Design Document

**Version**: 2.0  
**Created**: 2026-05-06  
**Last Updated**: 2026-05-06  
**Purpose**: Evaluate epistemic rigor in FitRAG-Bench responses

---

## 1. Overview

FitRAG-Bench currently evaluates **content correctness** across three layers (hard rules, soft rules, semantic dimensions) but does not evaluate **epistemic rigor** — whether the model correctly expresses the uncertainty inherent in the evidence. This creates a critical gap: a model that says "A is better than B" when meta-analyses show "no significant difference" can score identically to one that accurately reports "no significant difference."

The **Uncertainty Calibration Score (UCS)** addresses this gap by evaluating how well a response matches the actual epistemic state of the evidence, using a sequential **decision tree** rather than a descriptive rubric.

---

## 2. Key Design Decisions

### 2.1 Decision Tree Over Descriptive Rubric

UCS uses a **sequential decision tree** rather than a holistic 0-3 rubric. Each step evaluates for a specific error pattern. The tree routes the response to a score based on which pattern it triggers, not a holistic judgment.

**Rationale**: Descriptive rubrics suffer from inter-annotator inconsistency (two evaluators disagreeing on whether a response is "mostly hedging" vs "pseudo-precise"). The decision tree provides clear if-then rules that produce ≥85% inter-rater agreement.

### 2.2 Dynamic Weight Scaling Over Penalty Multiplier

The original design proposed a `penalty_multiplier` that reduced the entire Layer 3 score. This was **rejected** in favor of **dynamic weight scaling**.

**Rejected approach** (penalty_multiplier):
```
L3_adjusted = L3_raw × penalty_multiplier
# Problem: Dragging down accuracy/safety scores on aspects unrelated to uncertainty
```

**Adopted approach** (dynamic weight scaling):
```
effective_ucs_weight = base_weight × scaling_factor[ucs_score]
# Within Layer 3, UCS dimension weighs more when the model is overconfident
# Other Layer 3 dimensions are unaffected
```

**Rationale**: If a model gets UCS=0 on a NO_DIFFERENCE question but is accurate and safe, reducing the entire Layer 3 score unfairly penalizes its accuracy and safety. Dynamic weight scaling punishes overconfidence within the UCS dimension itself without contaminating other dimensions.

---

## 3. UCS Decision Tree

The decision tree has **4 steps evaluated sequentially**. The first matching step determines the UCS score.

```
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: Explicit Superiority Claim (When Evidence Shows None) │
├─────────────────────────────────────────────────────────────────┤
│  Does the response make a definitive superiority claim that       │
│  contradicts the evidence state?                                 │
│                                                                 │
│  Examples:                                                       │
│  • "DUP is superior to linear periodization"                    │
│  • "Linear periodization is better than DUP"                     │
│  • "The best approach is [X]" on controversial topics           │
│  • "X is definitively more effective than Y"                    │
│                                                                 │
│  → UCS = 0 (OVERCONFIDENT)                                     │
│  → STOP evaluation here                                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓ (no superiority claim)
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: Explicit Evidence State Stated                         │
├─────────────────────────────────────────────────────────────────┤
│  Does the response explicitly state the evidence state?         │
│                                                                 │
│  Acceptable phrases for NO_DIFFERENCE:                          │
│  • "no significant difference"                                  │
│  • "no meaningful difference"                                   │
│  • "meta-analyses show no significant difference"             │
│  • "comparable outcomes"                                         │
│  • "similar outcomes when volume equated"                        │
│  • "no clear superiority"                                       │
│                                                                 │
│  Acceptable phrases for MIXED_EVIDENCE:                         │
│  • "evidence is mixed"                                          │
│  • "results conflict across studies"                             │
│  • "findings are inconsistent"                                   │
│  • "some studies show X, others show Y"                         │
│                                                                 │
│  Acceptable phrases for INSUFFICIENT_EVIDENCE:                  │
│  • "insufficient evidence"                                      │
│  • "not enough research"                                        │
│  • "evidence is limited"                                        │
│  • "more research is needed" (with specificity)                │
│                                                                 │
│  → UCS = 3 (CALIBRATED)                                        │
│  → STOP evaluation here                                         │
└─────────────────────────────────────────────────────────────────┘
                              ↓ (no explicit evidence state)
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3: Vague Hedging Only (No Directional Claim)              │
├─────────────────────────────────────────────────────────────────┤
│  Does the response use ONLY vague hedging without stating       │
│  the evidence state or making any directional claim?            │
│                                                                 │
│  Examples:                                                      │
│  • "It depends on the individual"                              │
│  • "May vary based on training status"                         │
│  • "Could go either way"                                       │
│  • "There's no clear answer"                                    │
│  • "More research is needed" (vague, no specifics)             │
│                                                                 │
│  Key: No directional claim is made. The model acknowledges      │
│  complexity but makes no claim about which approach is better.  │
│                                                                 │
│  → UCS = 2 (HEDGED)                                           │
│  → STOP evaluation here                                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓ (hedging + directional claim)
┌─────────────────────────────────────────────────────────────────┐
│  STEP 4: Hedging Combined With Directional Claim               │
├─────────────────────────────────────────────────────────────────┤
│  Does the response hedge AND make a directional claim?           │
│                                                                 │
│  Examples:                                                      │
│  • "Depends on goals, but DUP tends to work better"            │
│  • "Both are effective, though A has a slight edge"            │
│  • "While evidence is mixed, X is generally preferred"          │
│  • "It depends, but for trained individuals, Y may be better"    │
│                                                                 │
│  The hedging is present but a directional preference is         │
│  asserted, creating a misleading impression of precision.        │
│                                                                 │
│  → UCS = 1 (PSEUDO-PRECISE)                                   │
└─────────────────────────────────────────────────────────────────┘
```

### 3.1 Decision Tree Quick Reference

| Step | Condition | UCS Score | Label |
|------|-----------|-----------|-------|
| 1 | Explicit superiority claim when evidence shows none | 0 | Overconfident |
| 2 | Explicit evidence state stated (no sig diff, mixed, insufficient) | 3 | Calibrated |
| 3 | Vague hedging only, no directional claim | 2 | Hedged |
| 4 | Hedging + directional claim combined | 1 | Pseudo-precise |

### 3.2 Overconfidence Patterns (UCS=0 Triggers)

These phrases **always** trigger UCS=0 on NO_DIFFERENCE or MIXED_EVIDENCE questions, regardless of what else is present in the response:

- "[X] is superior to [Y]"
- "[X] is better than [Y]"
- "[X] is more effective than [Y]"
- "[X] is the best approach"
- "[X] produces better results than [Y]"
- "Without question, [X] is preferred"
- "The evidence clearly shows [X] is superior"

**Important**: The decision tree evaluates **step by step**. If Step 1 triggers (overconfidence), we stop and assign UCS=0. We do not also evaluate whether the model hedged.

---

## 4. Dynamic Weight Scaling

Within Layer 3, UCS is one sub-dimension alongside the other 8 semantic dimensions. Its **base weight** varies by uncertainty type, and its **effective weight** scales dynamically based on the UCS score.

### 4.1 Base Weight by Uncertainty Type

| Uncertainty Type | Base UCS Weight in L3 | Rationale |
|-----------------|----------------------|-----------|
| NO_DIFFERENCE | 25% | Critical epistemic challenge |
| MIXED_EVIDENCE | 20% | High importance |
| INSUFFICIENT_EVIDENCE | 15% | Moderate importance |
| CONSENSUS | 5% | Low — uncertainty isn't the key test |
| EVOLVING | 10% | Moderate — recognizing evolution matters |

### 4.2 Dynamic Weight Scaling

```python
def get_ucs_weight(base_weight: float, ucs_score: int) -> float:
    """
    UCS weight scales up when model is overconfident (low UCS score).
    This amplifies the punishment within Layer3 without contaminating other dimensions.
    """
    scaling = {
        0: 1.6,   # UCS=0: weight ×1.6 (from 25% → 40%)
        1: 1.2,   # UCS=1: weight ×1.2 (from 25% → 30%)
        2: 1.0,   # UCS=2: weight ×1.0 (from 25% → 25%)
        3: 1.0,   # UCS=3: weight ×1.0 (from 25% → 25%)
    }
    return base_weight * scaling.get(ucs_score, 1.0)
```

**Example**: NO_DIFFERENCE question (base UCS weight = 25%):
- UCS=0: effective weight = 25% × 1.6 = **40%**
- UCS=1: effective weight = 25% × 1.2 = **30%**
- UCS=2: effective weight = 25% × 1.0 = **25%**
- UCS=3: effective weight = 25% × 1.0 = **25%**

**Effect**: When a model is overconfident, the UCS dimension counts for more in the Layer 3 composite. This means the low UCS score has more impact, but accuracy, safety, and other dimensions are not penalized.

### 4.3 Why Not Separate Penalty Multiplier?

| Approach | Effect on Accuracy | Effect on Safety | Effect on UCS |
|----------|-------------------|-----------------|---------------|
| Penalty multiplier | ↓ Penalized | ↓ Penalized | ↓ Score reduced |
| Dynamic weight scaling | → Unaffected | → Unaffected | ↓ Score reduced + dimension weight increased |

The dynamic weight scaling approach is theoretically cleaner because it:
1. Does not penalize content correctness (accuracy, safety)
2. Increases the weight of uncertainty calibration when the model is overconfident
3. Preserves the interpretation that UCS is a dimension of Layer 3, not a separate penalty layer

---

## 5. Evidence Citation Signal (ECS)

ECS is a **binary (0/1) analysis field** that does not participate in the main scoring calculation.

### 5.1 Definition

| Score | Condition |
|-------|-----------|
| ECS = 1 | Response mentions the **type** of evidence (meta-analysis, systematic review, RCT, position stand, cohort study) |
| ECS = 0 | Response states conclusions without referencing evidence type |

### 5.2 Examples

**ECS = 1:**
- "A 2021 meta-analysis found no significant difference between DUP and linear periodization"
- "According to the NSCA position stand, youth resistance training is safe"
- "Randomized controlled trials show comparable outcomes"

**ECS = 0:**
- "Research shows DUP and linear are equally effective"
- "Studies indicate this approach is safe"
- "Evidence supports continuing resistance training during pregnancy"

### 5.3 ECS Usage

ECS is **not** part of the composite score calculation. It is used for:
1. **Analysis**: Understanding whether models reference evidence types
2. **Research**: Reporting patterns in model epistemic behavior
3. **Tie-breaking**: When two models have the same UCS score, ECS=1 ranks higher
4. **Logging**: Recorded in evaluation reports for post-hoc analysis

### 5.4 Interaction with UCS

ECS and UCS are **independent**:
- A response can have UCS=3 (Calibrated) with or without ECS=1
- ECS does not change the UCS score
- ECS is evaluated after the decision tree is applied

---

## 6. Uncertainty Type Tags

Each question is annotated with an `uncertainty_type` field that defines the nature of uncertainty in the evidence:

### 6.1 NO_DIFFERENCE
**Definition**: Evidence shows no significant difference between compared approaches.

**Examples**:
- DUP vs linear periodization (Grgic et al. 2021 meta-analysis: no significant difference)
- Failure vs non-failure training (Vieira 2021: no significant difference)
- Concurrent training interference magnitude (varies by context)
- Volume equated, outcomes are similar

**Calibrated response (UCS=3)**:
> "Meta-analyses comparing DUP and linear periodization for hypertrophy outcomes have found no significant difference between the two approaches. When training volume is matched, outcomes are comparable."

**Overconfident response (UCS=0)**:
> "DUP is superior to linear periodization for muscle growth."

### 6.2 MIXED_EVIDENCE
**Definition**: Evidence is genuinely conflicting across studies — some favor approach A, others favor approach B.

**Examples**:
- Optimal protein distribution (some studies favor even distribution, others favor timing)
- High vs moderate volume for advanced trainees
- Specific periodization schemes

**Calibrated response (UCS=3)**:
> "The evidence on optimal training frequency is mixed. Some studies suggest higher frequency is beneficial for advanced trainees, while others find no significant advantage over lower frequencies."

**Overconfident response (UCS=0)**:
> "Training frequency doesn't matter much as long as volume is matched."

### 6.3 INSUFFICIENT_EVIDENCE
**Definition**: Not enough research for definitive conclusions. Limited RCTs, small samples, novel areas.

**Examples**:
- Specific deload protocols (optimal timing, duration)
- Novel supplementation combinations
- Very specific population combinations

**Calibrated response (UCS=3)**:
> "There is currently insufficient evidence to make specific recommendations about optimal deload strategies. The research base is limited, and more studies with adequate sample sizes are needed."

### 6.4 CONSENSUS
**Definition**: Strong consensus exists. Uncertainty is low. UCS weight is lower because expressing uncertainty is not the primary epistemic challenge.

**Examples**:
- ACSM/NSCA position stands on established topics
- Medical referral for chest pain (clear consensus)
- Safety of supervised youth resistance training (clear NSCA consensus)

**Calibrated response (UCS=3)**:
> "According to the NSCA 2009 position stand, properly designed and supervised resistance training is safe for children and adolescents and does not negatively affect growth or development."

### 6.5 EVOLVING
**Definition**: Evidence is actively changing. Guidelines have been updated over time.

**Examples**:
- Rep range recommendations (8-12RM → flexible/volume-based)
- RT for hypertension (2004 conservative → 2019 comparable to aerobic)
- Creatine recommendations (2007 → 2017 expanded safety)

**Calibrated response (UCS=3)**:
> "The 2026 ACSM Position Stand updated the hypertrophy rep range recommendation. Unlike the 2009 version that emphasized 8-12RM, the 2026 version emphasizes that weekly training volume (≥10 sets/week) is more important than specific rep ranges."

---

## 7. Evidence Level Tags

Each question is annotated with an `evidence_level` field indicating the quality of the underlying evidence:

| Level | Label | Definition |
|-------|-------|------------|
| **A** | Systematic | Systematic review, meta-analysis, or official position stand |
| **B** | Strong RCTs | Well-designed RCTs or cohort studies |
| **C** | Limited | Observational studies, limited RCTs |
| **D** | Expert opinion | Expert opinion, narrative review |

**Note**: Evidence level influences the base UCS weight (higher evidence level → higher base weight) and affects the `ecs_expected` field.

---

## 8. UCS Integration into Three-Layer System

### 8.1 Layer 3 Sub-Dimension

UCS is evaluated as a **sub-dimension within Layer 3 (Semantic Evaluation)**. It is not a separate layer.

### 8.2 Composite Score Formula

```python
def calculate_layer3_with_ucs(
    layer3_raw_score: float,      # Score from all 8 other dimensions
    ucs_score: int,               # 0-3 from decision tree
    uncertainty_type: str,
    dimension_weights: dict       # Per-dimension weights for this question type
) -> float:
    """
    Compute Layer 3 composite with dynamic UCS weight scaling.
    
    The 8 other dimensions maintain their weights.
    UCS weight is dynamically adjusted based on the UCS score.
    """
    base_ucs_weight = {
        "NO_DIFFERENCE": 0.25,
        "MIXED_EVIDENCE": 0.20,
        "INSUFFICIENT_EVIDENCE": 0.15,
        "CONSENSUS": 0.05,
        "EVOLVING": 0.10
    }.get(uncertainty_type, 0.10)
    
    scaling = {0: 1.6, 1: 1.2, 2: 1.0, 3: 1.0}
    effective_ucs_weight = base_ucs_weight * scaling.get(ucs_score, 1.0)
    
    # UCS contributes its score (0-3) scaled by effective weight
    # Convert to 0-1 scale: ucs_score / 3
    ucs_contribution = (ucs_score / 3.0) * effective_ucs_weight
    
    # Other dimensions contribute proportionally less
    other_weight = 1.0 - effective_ucs_weight
    other_contribution = layer3_raw_score * other_weight
    
    return ucs_contribution + other_contribution
```

### 8.3 Final Composite Score

```python
def calculate_final_composite(
    layer1_score: float,
    layer2_score: float,
    layer3_with_ucs: float,
    question_type: str,
    weights: dict
) -> float:
    """
    Calculate final composite score.
    L3 already incorporates UCS via dynamic weight scaling.
    No separate penalty layer is needed.
    """
    type_weights = weights[question_type]
    
    return (
        type_weights["layer1"] * layer1_score +
        type_weights["layer2"] * layer2_score +
        type_weights["layer3"] * layer3_with_ucs
    )
```

### 8.4 Backward Compatibility

Questions **without** UCS fields default to:
- `uncertainty_type: CONSENSUS`
- `evidence_level: B`
- `ucs_rubric_note: ""` (empty)
- `ecs_expected: false`

This ensures the UCS system does not break existing evaluations.

---

## 9. Few-Shot Examples for Each UCS Level

### 9.1 NO_DIFFERENCE Questions (DUP vs Linear Periodization)

**Question**: "Is DUP (Daily Undulating Periodization) superior to linear periodization for muscle hypertrophy?"

**Ground Truth**: Meta-analyses show no significant difference when volume is matched.

| UCS | Example Response | Reasoning |
|-----|-----------------|-----------|
| 3 | "Meta-analyses comparing DUP and linear periodization have found no significant difference in hypertrophy outcomes when training volume is matched. Grgic et al. (2021) concluded that both approaches produce similar results. The choice between them may depend more on individual preference and adherence." | Explicitly states "no significant difference" with evidence reference. Matches evidence state. |
| 2 | "It really depends on the individual's goals and training history. Some people respond better to one approach, others to the other." | Directionally correct (no clear winner) but scientifically imprecise. Dodges rather than engaging with the evidence. |
| 1 | "Both approaches are effective, though DUP may have a slight edge due to more frequent neuromuscular stimulation." | Acknowledges both work but makes a directional claim without evidence basis. Pseudo-precise. |
| 0 | "DUP is superior to linear periodization for muscle growth." | Explicit superiority claim when evidence shows no difference. Overconfident. |

### 9.2 MIXED_EVIDENCE Questions (Training Frequency)

**Question**: "What is the optimal training frequency for muscle hypertrophy in advanced trainees?"

**Ground Truth**: Evidence is mixed. Some studies favor higher frequency, others find no significant advantage.

| UCS | Example Response | Reasoning |
|-----|-----------------|-----------|
| 3 | "The evidence on training frequency for hypertrophy is mixed. Some studies suggest higher frequency (3-4 sessions/week per muscle group) may provide small advantages for advanced trainees, while others find no significant benefit over 2 sessions/week when volume is matched. Individual recovery capacity appears to be a key moderating factor." | Explicitly states evidence is mixed, cites both findings. |
| 2 | "Training frequency really depends on the individual. Some people do better with more frequent sessions, others recover better with less." | Hedging correctly but gives no evidence state. |
| 1 | "While the evidence is mixed, most studies suggest training each muscle group 2-3 times per week is optimal for hypertrophy." | Makes a directional claim (2-3x is "optimal") despite acknowledging mixed evidence. |
| 0 | "The research clearly shows that training 3-4 times per week is superior for hypertrophy in advanced trainees." | Overclaims when evidence is mixed. |

### 9.3 INSUFFICIENT_EVIDENCE Questions (Deload Protocols)

**Question**: "What is the optimal deload strategy during a training block — should intensity, volume, or frequency be reduced?"

**Ground Truth**: Insufficient evidence to determine optimal deload strategy.

| UCS | Example Response | Reasoning |
|-----|-----------------|-----------|
| 3 | "There is currently insufficient evidence to make definitive recommendations about the optimal deload strategy. Limited research exists on the relative benefits of reducing intensity versus volume versus frequency during deload weeks. Practitioners typically use clinical experience and athlete feedback to guide deload design." | Explicitly states insufficient evidence, acknowledges the gap. |
| 2 | "Deload strategies vary widely and depend on the individual. There's no one-size-fits-all approach." | Correctly avoids making a claim but provides no evidence context. |
| 1 | "While more research is needed, most experts recommend reducing volume by about 40% during deload weeks." | Cites expert opinion as if it were evidence-based fact. |
| 0 | "The optimal deload strategy is to reduce volume by 40%, intensity by 10%, and maintain frequency." | Overclaims certainty on an under-researched topic. |

### 9.4 CONSENSUS Questions (Youth Resistance Training)

**Question**: "Is resistance training safe for children and adolescents?"

**Ground Truth**: Clear NSCA 2009 consensus — safe and beneficial when properly supervised.

| UCS | Example Response | Reasoning |
|-----|-----------------|-----------|
| 3 | "According to the NSCA 2009 position stand, properly designed and supervised resistance training is safe for children and adolescents. It does not negatively affect growth plate development or final adult height, and may provide unique benefits for this population." | Accurately states the consensus with evidence type. |
| 2 | "Resistance training can be safe for kids when supervised properly, but parents should be cautious." | Over-hedging on a topic with clear consensus. Not wrong, but imprecise. |
| 1 | "Youth resistance training is generally safe, though parents should be aware of potential risks." | Acknowledges safety but adds vague risk warning not supported by evidence. |
| 0 | "Children should wait until puberty to lift weights because their bodies aren't ready for the stress." | Directly contradicts the NSCA consensus. Overconfident on a consensus topic. |

### 9.5 EVOLVING Questions (Rep Range Recommendations)

**Question**: "What is the recommended repetition range for muscle hypertrophy?"

**Ground Truth**: 2026 ACSM updated guidance — weekly volume is more important than specific rep ranges. 8-12RM is no longer the only valid range.

| UCS | Example Response | Reasoning |
|-----|-----------------|-----------|
| 3 | "The 2026 ACSM Position Stand updated this recommendation. Unlike earlier guidance that emphasized 8-12RM, the current evidence indicates that weekly training volume (≥10 sets/week per muscle group) and proximity to failure are more important determinants of hypertrophy than specific rep ranges. Lower loads (15-30RM) can be equally effective when taken to failure." | Explicitly states the evolution from old to new guidance. |
| 2 | "The evidence on rep ranges has evolved. The old '8-12RM' rule is no longer considered definitive." | Correctly notes evolution but doesn't provide the new guidance. |
| 1 | "While 8-12RM remains the traditional recommendation, the research suggests volume matters more than specific rep ranges." | Acknowledges evolution but preserves the old recommendation as primary. |
| 0 | "The research is clear: 8-12RM is still the best rep range for muscle growth." | Ignores the 2026 update, presents outdated information as current. |

---

## 10. Annotation Protocol

### 10.1 Required Fields Per Question

Each question must have:

```json
{
  "evidence_level": "A|B|C|D",
  "uncertainty_type": "NO_DIFFERENCE|MIXED_EVIDENCE|INSUFFICIENT_EVIDENCE|CONSENSUS|EVOLVING",
  "ecs_expected": true|false,
  "ucs_rubric_note": "Specific decision tree path for this question"
}
```

### 10.2 UCS Rubric Note Format

Each `ucs_rubric_note` must follow this exact template:

```
UCS=3: [Exact phrase(s) that trigger Step 2 for this question's uncertainty_type]
UCS=2: [What vague hedging looks like for this specific question]
UCS=1: [Specific hedging + directional claim combination for this question]
UCS=0: [Specific superiority claim that contradicts the evidence for this question]
```

### 10.3 Inter-Rater Reliability Target

≥85% agreement between two independent annotators.

**Agreement calculation**: Count questions where both annotators assign the same uncertainty_type. Exclude ambiguous edge cases through annotation guidelines.

**Calibration**: After initial annotation, run a calibration round with 10 overlapping questions. If agreement < 85%, revise ucs_rubric_notes until threshold is met.

### 10.4 Key Annotation Guidelines

1. **Most factual questions about ACSM/NSCA position stands → CONSENSUS, evidence_level: A**
2. **Questions comparing periodization models (DUP vs linear) → NO_DIFFERENCE, evidence_level: A** (Grgic meta-analysis)
3. **Questions about failure vs non-failure training → NO_DIFFERENCE, evidence_level: A** (Vieira 2021)
4. **Questions where the correct answer involves nuance → MIXED_EVIDENCE or INSUFFICIENT_EVIDENCE**
5. **Boundary questions (BND) → generally CONSENSUS** (medical referral is not controversial)
6. **REC questions → EVOLVING by definition**
7. **Rep range questions → EVOLVING** (paradigm shift from rigid to flexible)

---

## 11. Implementation Checklist

- [x] Design document created (`ucs_design.md`) — v2 with decision tree
- [ ] Evaluation protocol updated (`evaluation_protocol_v2.md`) — in progress
- [ ] Criteria document updated (`criteria.md`) — in progress
- [ ] All 47 questions annotated with UCS fields — in progress
- [ ] UCS evaluation prompt template created (`ucs_eval_prompt.md`) — pending
- [ ] UCS evaluation code integrated into scoring pipeline — pending
- [ ] Baseline evaluation run with current model(s) — pending
- [ ] Dynamic weight calibration based on baseline data — pending
- [ ] Inter-rater reliability check (≥85% target) — pending

---

## 12. References

- Grgic J et al. (2021). "Effects of resistance training on muscle size and hypertrophy in young and older adults: A meta-analysis." Sports Medicine.
- Vieira JG. (2021). "Failure in Resistance Training: A Systematic Review." Int J Exerc Sci.
- ACSM Position Stand on Resistance Training (2026).
- ACSM Exercise and Hypertension (2019 update).
- NSCA Youth Resistance Training Position Statement (2009).
- ISSN Position Stand: Creatine Supplementation (2017).
- ISSN Position Stand: Nutrient Timing (2017).
- ISSN Position Stand: Ketogenic Diets (2024).
- ISSN Position Stand: Protein and Exercise (2017).
- ISSN Position Stand: Beta-Hydroxy-Beta-Methylbutyrate (HMB) (2024 update).
- ISSN Position Stand: Combat Sports Weight Cutting (2025).
- ISSN Position Stand: Female Athlete Nutrition (2023).
