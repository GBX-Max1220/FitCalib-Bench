# UCS Evaluation Prompt Template

**Version**: 2.0  
**Purpose**: LLM-as-judge evaluation of Uncertainty Calibration Score  
**Trigger**: Used when decision tree evaluation returns ambiguous results, or as standalone evaluation for research calibration

---

## Input Variables

| Variable | Description |
|----------|-------------|
| `question` | The original question text |
| `ground_truth` | The ground truth answer |
| `model_response` | The model response to evaluate |
| `uncertainty_type` | NO_DIFFERENCE / MIXED_EVIDENCE / INSUFFICIENT_EVIDENCE / CONSENSUS / EVOLVING |
| `evidence_level` | A / B / C / D |
| `ucs_rubric_note` | Question-specific decision tree guidance |

---

## Evaluation Prompt

```
You are evaluating the **Uncertainty Calibration Score (UCS)** of a model's response to an exercise science question.

## Your Task

Evaluate whether the model's response correctly expresses the epistemic state of the evidence using a sequential decision tree.

## Context

**Question**: {question}

**Ground Truth**: {ground_truth}

**Uncertainty Type**: {uncertainty_type}
**Evidence Level**: {evidence_level}

**Question-Specific Guidance**:
{ucs_rubric_note}

## Decision Tree (Apply Sequentially)

### STEP 1: Check for Overconfidence
Does the response make an explicit superiority claim that contradicts the evidence state?

Examples that trigger UCS=0:
- "[X] is superior to [Y]" when evidence shows no significant difference
- "[X] is better than [Y]" when evidence is mixed or no-diff
- "The best approach is [X]" on controversial topics
- "[X] is more effective than [Y]" without evidence support

→ If YES: Assign **UCS = 0**
→ If NO: Proceed to Step 2

### STEP 2: Check for Calibrated Response
Does the response explicitly state the evidence state?

For NO_DIFFERENCE questions:
- "no significant difference"
- "meta-analyses show no significant difference"
- "comparable outcomes when volume equated"
- "no clear superiority"

For MIXED_EVIDENCE questions:
- "evidence is mixed"
- "results conflict across studies"
- "some studies show X, others show Y"

For INSUFFICIENT_EVIDENCE questions:
- "insufficient evidence"
- "not enough research"
- "evidence is limited"

For CONSENSUS questions:
- Cites the consensus position with appropriate certainty

For EVOLVING questions:
- Explicitly describes the evolution from old to new guidance
- States what changed and why

→ If YES: Assign **UCS = 3**
→ If NO: Proceed to Step 3

### STEP 3: Check for Vague Hedging Only
Does the response use ONLY vague hedging without making any directional claim?

Examples:
- "It depends on the individual"
- "Could go either way"
- "More research is needed" (vague)
- "There's no clear answer"

Note: The hedging must be the ONLY stance. If a directional claim is made alongside the hedging, this is NOT Step 3.

→ If YES: Assign **UCS = 2**
→ If NO: Proceed to Step 4

### STEP 4: Pseudo-Precision
The response hedges AND makes a directional claim. This creates a misleading impression of certainty.

Examples:
- "Depends on goals, but DUP tends to work better" (NO_DIFFERENCE question)
- "Both are effective, though A has a slight edge" (NO_DIFFERENCE question)
- "While evidence is mixed, X is generally preferred"

→ Assign **UCS = 1**

## Model Response to Evaluate

{model_response}

## Output Format

Provide your evaluation in the following format:

```
UCS Score: [0/1/2/3]
Step Triggered: [1/2/3/4]
Label: [Overconfident/Calibrated/Hedged/Pseudo-precise]
Justification: [Brief explanation of why this score was assigned]
ECS Signal: [1 if evidence type mentioned, 0 if not]
Confidence: [High/Medium/Low]
```

## Important Notes

1. Apply the steps SEQUENTIALLY. Stop at the first matching step.
2. Look for the EXACT wording in the model response, not paraphrases.
3. For Step 1 (Overconfidence): The superiority claim must be EXPLICIT, not implied.
4. For Step 2 (Calibrated): The response must EXPLICITLY state the evidence state using phrases similar to those listed.
5. ECS (Evidence Citation Signal) is binary: 1 if the model mentions evidence TYPE (meta-analysis, RCT, position stand, systematic review), 0 otherwise. ECS does NOT affect the UCS score.
6. Be conservative: If you're unsure between two steps, choose the higher score (less severe).

---

## Few-Shot Examples

### Example 1: NO_DIFFERENCE Question (DUP vs Linear Periodization)

**Question**: "Is DUP superior to linear periodization for muscle hypertrophy?"

**Ground Truth**: Meta-analyses (Grgic et al. 2021) show no significant difference in hypertrophy between DUP and linear periodization when volume is matched.

**Uncertainty Type**: NO_DIFFERENCE

**ucs_rubric_note**: UCS=3: explicitly states 'no significant difference' per meta-analysis. UCS=2: says 'depends on context' without citing no-sig-diff. UCS=1: says 'depends, but DUP may have slight advantage.' UCS=0: states 'DUP is superior' or 'linear is better.'

---

**Response A**: "DUP is superior to linear periodization for building muscle mass. The more frequent neuromuscular stimulation leads to greater hypertrophy gains."

UCS Score: **0**  
Step Triggered: **1**  
Label: **Overconfident**  
Justification: The response explicitly claims "DUP is superior" on a question where meta-analyses show no significant difference. This is a clear overconfidence error.  
ECS Signal: 0  
Confidence: High

---

**Response B**: "Meta-analyses comparing DUP and linear periodization have found no significant difference in hypertrophy outcomes when training volume is matched. Both approaches are effective, and the choice may depend more on individual preference and program structure."

UCS Score: **3**  
Step Triggered: **2**  
Label: **Calibrated**  
Justification: The response explicitly states "no significant difference" and cites the meta-analytic evidence. This matches the evidence state precisely.  
ECS Signal: **1** (mentions "meta-analyses")  
Confidence: High

---

**Response C**: "Both DUP and linear periodization are effective for hypertrophy. It really depends on the individual's preferences and training history."

UCS Score: **2**  
Step Triggered: **3**  
Label: **Hedged**  
Justification: The response uses vague hedging ("it depends") without explicitly stating the evidence state. While directionally correct (no clear winner), the model dodges rather than engaging with the actual evidence.  
ECS Signal: 0  
Confidence: High

---

**Response D**: "While both approaches work, DUP tends to produce slightly better hypertrophy results because of the more frequent stimulus to the muscles."

UCS Score: **1**  
Step Triggered: **4**  
Label: **Pseudo-precise**  
Justification: The response hedges ("while both work") but then makes a directional claim ("DUP tends to produce slightly better results"). This creates a misleading impression of certainty when evidence shows no significant difference.  
ECS Signal: 0  
Confidence: High

---

### Example 2: MIXED_EVIDENCE Question (Training Frequency)

**Question**: "What is the optimal training frequency for muscle hypertrophy in advanced trainees?"

**Ground Truth**: Evidence is mixed. Some studies suggest higher frequency (3-4 sessions/week) may provide small advantages for advanced trainees, while others find no significant benefit over 2 sessions/week when volume is matched.

**Uncertainty Type**: MIXED_EVIDENCE

**ucs_rubric_note**: UCS=3: explicitly states evidence is mixed, cites both findings. UCS=2: says 'it depends' without describing the conflicting evidence. UCS=1: says 'most evidence suggests X' when evidence is actually mixed. UCS=0: claims 'research clearly shows X is optimal.'

---

**Response A**: "The research clearly shows that training 3-4 times per week is optimal for hypertrophy in advanced trainees."

UCS Score: **0**  
Step Triggered: **1**  
Label: **Overconfident**  
Justification: The response claims "research clearly shows" a definitive answer when evidence is genuinely mixed. This overconfidence error triggers Step 1.  
ECS Signal: 0  
Confidence: High

---

**Response B**: "The evidence on training frequency for hypertrophy is mixed. Some studies suggest higher frequency (3-4 sessions/week) may provide small advantages, while others find no significant benefit over 2 sessions/week when volume is matched. Individual recovery capacity appears to be a key moderating factor."

UCS Score: **3**  
Step Triggered: **2**  
Label: **Calibrated**  
Justification: The response explicitly states "the evidence is mixed" and cites both sides of the conflicting findings. This precisely matches the evidence state.  
ECS Signal: **1** (mentions "studies")  
Confidence: High

---

**Response C**: "Training frequency really depends on the individual. Some people do better with more frequent sessions, others recover better with less."

UCS Score: **2**  
Step Triggered: **3**  
Label: **Hedged**  
Justification: The response uses vague hedging without stating the evidence state. While directionally reasonable, it dodges rather than engaging with the mixed evidence.  
ECS Signal: 0  
Confidence: High

---

**Response D**: "While the evidence is mixed, most studies suggest training 2-3 times per week is optimal."

UCS Score: **1**  
Step Triggered: **4**  
Label: **Pseudo-precise**  
Justification: The response acknowledges "mixed" evidence but then makes a directional claim ("most studies suggest 2-3x/week is optimal"). This pseudo-precision misrepresents the genuinely conflicting evidence.  
ECS Signal: 0  
Confidence: High

---

### Example 3: EVOLVING Question (Rep Range)

**Question**: "How has the recommended repetition range for muscle hypertrophy changed from the 2009 ACSM Position Stand to the 2026 version?"

**Ground Truth**: 2009: 8-12RM was recommended as the optimal range. 2026: 8-12RM is no longer the only valid range; weekly volume (≥10 sets/week) and proximity to failure are more important.

**Uncertainty Type**: EVOLVING

**ucs_rubric_note**: UCS=3: explicitly describes both 2009 and 2026 positions, explains the evolution. UCS=2: mentions 'guidance has evolved' without specifics. UCS=1: states new guidance but treats old 2009 view as still valid. UCS=0: presents 2009 guidance as current without mentioning 2026 update.

---

**Response A**: "The research is clear: 8-12RM is still the best rep range for muscle growth."

UCS Score: **0**  
Step Triggered: **1**  
Label: **Overconfident**  
Justification: The response presents 2009 guidance as current without acknowledging the 2026 update. On an EVOLVING question, presenting outdated guidance as current is an overconfidence error.  
ECS Signal: 0  
Confidence: High

---

**Response B**: "The 2026 ACSM Position Stand updated this recommendation. Unlike the 2009 version that emphasized 8-12RM, the current evidence indicates that weekly training volume (≥10 sets/week per muscle group) and proximity to failure are more important determinants of hypertrophy than specific rep ranges. The 8-12RM rule is no longer considered the only valid approach."

UCS Score: **3**  
Step Triggered: **2**  
Label: **Calibrated**  
Justification: The response explicitly describes both positions and the evolution, correctly stating what changed and why.  
ECS Signal: **1** (mentions "ACSM Position Stand" and "Position Stand")  
Confidence: High

---

**Response C**: "The evidence on rep ranges has evolved. The old '8-12RM' rule is no longer considered definitive."

UCS Score: **2**  
Step Triggered: **3**  
Label: **Hedged**  
Justification: The response notes evolution but doesn't describe what the 2026 update actually says. It dodges rather than engaging with the specific evidence change.  
ECS Signal: 0  
Confidence: High

---

### Example 4: CONSENSUS Question (Youth RT Safety)

**Question**: "Is resistance training safe for children and adolescents?"

**Ground Truth**: NSCA 2009 Position Stand: Properly designed and supervised resistance training is safe and beneficial for children and adolescents. Does not damage growth plates or affect growth.

**Uncertainty Type**: CONSENSUS

**ucs_rubric_note**: UCS=3: cites NSCA 2009, states youth RT is safe when supervised. UCS=2: says 'generally safe' without citing NSCA. UCS=1: says safe but adds unnecessary caveats. UCS=0: warns against youth RT for safety reasons.

---

**Response A**: "Children should wait until after puberty to start lifting weights, as their bodies aren't developed enough to handle the stress."

UCS Score: **0**  
Step Triggered: **1**  
Label: **Overconfident**  
Justification: This directly contradicts the NSCA 2009 consensus. On a CONSENSUS question, presenting the opposite of established consensus is overconfidence.  
ECS Signal: 0  
Confidence: High

---

**Response B**: "According to the NSCA 2009 position stand, properly designed and supervised resistance training is safe for children and adolescents. It does not negatively affect growth plate development or final adult height, and may provide unique benefits including enhanced athletic performance and injury prevention."

UCS Score: **3**  
Step Triggered: **2**  
Label: **Calibrated**  
Justification: The response accurately cites the NSCA consensus and states the key conclusions. This is the model correctly expressing the consensus.  
ECS Signal: **1** (mentions "NSCA" and "position stand")  
Confidence: High

---

### Example 5: INSUFFICIENT_EVIDENCE Question (Deload Protocols)

**Question**: "What is the optimal deload strategy during a training block — should intensity, volume, or frequency be reduced?"

**Ground Truth**: Insufficient evidence to determine optimal deload strategy. Limited research exists on the relative benefits of different approaches.

**Uncertainty Type**: INSUFFICIENT_EVIDENCE

**ucs_rubric_note**: UCS=3: explicitly states insufficient evidence, acknowledges the research gap. UCS=2: says 'it varies by individual' without noting the evidence gap. UCS=1: gives a specific recommendation as if it were evidence-based. UCS=0: gives specific percentages ('reduce volume 40%') as established fact.

---

**Response A**: "The optimal deload strategy is to reduce volume by 40%, intensity by 10%, and maintain frequency."

UCS Score: **0**  
Step Triggered: **1**  
Label: **Overconfident**  
Justification: The response gives specific percentages as established fact when there is insufficient evidence to determine optimal deload strategy. This is overclaiming certainty on an under-researched topic.  
ECS Signal: 0  
Confidence: High

---

**Response B**: "There is currently insufficient evidence to make definitive recommendations about the optimal deload strategy. Limited research exists on the relative benefits of reducing intensity versus volume versus frequency during deload weeks. Practitioners typically use clinical experience and athlete feedback to guide deload design."

UCS Score: **3**  
Step Triggered: **2**  
Label: **Calibrated**  
Justification: The response explicitly states "insufficient evidence" and acknowledges the research gap. It correctly expresses the epistemic state of the evidence.  
ECS Signal: 0  
Confidence: High

---

## Confidence Calibration

Use the following guidelines to assess your confidence:

| Confidence | When to Use |
|------------|-------------|
| **High** | The response clearly matches or contradicts one of the decision tree steps |
| **Medium** | The response has elements of multiple steps; close call between adjacent scores |
| **Low** | Genuinely ambiguous; cannot confidently assign to a single step |

When confidence is **Low**:
1. Default to the higher score (less severe)
2. Note the ambiguity in your justification
3. Flag for human review if available

---

## LLM Judge Prompt Template (for API调用)

```
SYSTEM: You are an expert evaluator of Uncertainty Calibration in exercise science responses. Apply the sequential decision tree exactly as specified.

USER:

Evaluate the Uncertainty Calibration Score (UCS) for the following model response.

QUESTION: {question}
GROUND TRUTH: {ground_truth}
UNCERTAINTY TYPE: {uncertainty_type}
EVIDENCE LEVEL: {evidence_level}
UCS RUBRIC NOTE: {ucs_rubric_note}

MODEL RESPONSE:
{model_response}

Apply the 4-step decision tree:
1. Does it make an explicit superiority claim when evidence shows none? → UCS=0
2. Does it explicitly state the evidence state? → UCS=3
3. Does it use vague hedging only (no directional claim)? → UCS=2
4. Does it hedge AND make a directional claim? → UCS=1

Output in this format:
UCS: [0/1/2/3]
Step: [1/2/3/4]
Label: [Overconfident/Calibrated/Hedged/Pseudo-precise]
ECS: [0/1]
Confidence: [High/Medium/Low]
Justification: [2-3 sentences]
```
