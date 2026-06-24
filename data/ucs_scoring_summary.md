# MaxFitCalib-Bench UCS Scoring Summary

**Scoring Model**: GPT-5.5 Instant (via OpenRouter)  
**Date**: 2026-05-18  
**Total Records**: 252 (126 questions × 2 models)

---

## 1. Overall UCS Distribution

| UCS Score | Label | Count | Percentage |
|-----------|-------|-------|------------|
| 0 | Overconfident | 0 | 0.0% |
| 1 | Pseudo-Precise | 16 | 6.3% |
| 2 | Hedged | 2 | 0.8% |
| 3 | Calibrated | 234 | 92.9% |

**Mean UCS**: 2.87 / 3.00

---

## 2. By Model

### deepseek-chat (126 questions)

**Mean UCS**: 2.87

| UCS Score | Label | Count | Percentage |
|-----------|-------|-------|------------|
| 0 | Overconfident | 0 | 0.0% |
| 1 | Pseudo-Precise | 7 | 5.6% |
| 2 | Hedged | 2 | 1.6% |
| 3 | Calibrated | 117 | 92.9% |

### qwen-plus (126 questions)

**Mean UCS**: 2.86

| UCS Score | Label | Count | Percentage |
|-----------|-------|-------|------------|
| 0 | Overconfident | 0 | 0.0% |
| 1 | Pseudo-Precise | 9 | 7.1% |
| 2 | Hedged | 0 | 0.0% |
| 3 | Calibrated | 117 | 92.9% |

---

## 3. By Uncertainty Type

### NO_DIFFERENCE (20 questions)

**Mean UCS**: 2.60

| UCS Score | Label | Count | Percentage |
|-----------|-------|-------|------------|
| 0 | Overconfident | 0 | 0.0% |
| 1 | Pseudo-Precise | 4 | 20.0% |
| 2 | Hedged | 0 | 0.0% |
| 3 | Calibrated | 16 | 80.0% |

### MIXED_EVIDENCE (42 questions)

**Mean UCS**: 2.64

| UCS Score | Label | Count | Percentage |
|-----------|-------|-------|------------|
| 0 | Overconfident | 0 | 0.0% |
| 1 | Pseudo-Precise | 7 | 16.7% |
| 2 | Hedged | 1 | 2.4% |
| 3 | Calibrated | 34 | 81.0% |

### INSUFFICIENT_EVIDENCE (8 questions)

**Mean UCS**: 2.25

| UCS Score | Label | Count | Percentage |
|-----------|-------|-------|------------|
| 0 | Overconfident | 0 | 0.0% |
| 1 | Pseudo-Precise | 3 | 37.5% |
| 2 | Hedged | 0 | 0.0% |
| 3 | Calibrated | 5 | 62.5% |

### EVOLVING (42 questions)

**Mean UCS**: 2.95

| UCS Score | Label | Count | Percentage |
|-----------|-------|-------|------------|
| 0 | Overconfident | 0 | 0.0% |
| 1 | Pseudo-Precise | 1 | 2.4% |
| 2 | Hedged | 0 | 0.0% |
| 3 | Calibrated | 41 | 97.6% |

### CONSENSUS (140 questions)

**Mean UCS**: 2.98

| UCS Score | Label | Count | Percentage |
|-----------|-------|-------|------------|
| 0 | Overconfident | 0 | 0.0% |
| 1 | Pseudo-Precise | 1 | 0.7% |
| 2 | Hedged | 1 | 0.7% |
| 3 | Calibrated | 138 | 98.6% |

---

## 4. Cross Analysis: Model × Uncertainty Type

| Model | Uncertainty Type | N | Mean UCS | UCS=0 | UCS=1 | UCS=2 | UCS=3 |
|-------|-----------------|---|----------|-------|-------|-------|-------|
| deepseek-chat | NO_DIFFERENCE | 10 | 2.60 | 0 | 2 | 0 | 8 |
| deepseek-chat | MIXED_EVIDENCE | 21 | 2.76 | 0 | 2 | 1 | 18 |
| deepseek-chat | INSUFFICIENT_EVIDENCE | 4 | 2.50 | 0 | 1 | 0 | 3 |
| deepseek-chat | EVOLVING | 21 | 2.90 | 0 | 1 | 0 | 20 |
| deepseek-chat | CONSENSUS | 70 | 2.96 | 0 | 1 | 1 | 68 |
| qwen-plus | NO_DIFFERENCE | 10 | 2.60 | 0 | 2 | 0 | 8 |
| qwen-plus | MIXED_EVIDENCE | 21 | 2.52 | 0 | 5 | 0 | 16 |
| qwen-plus | INSUFFICIENT_EVIDENCE | 4 | 2.00 | 0 | 2 | 0 | 2 |
| qwen-plus | EVOLVING | 21 | 3.00 | 0 | 0 | 0 | 21 |
| qwen-plus | CONSENSUS | 70 | 3.00 | 0 | 0 | 0 | 70 |

---

## 5. Key Observations

1. **No Overconfident (UCS=0) scores**: Both models avoided making explicit superiority claims that contradict evidence state. This could indicate genuine calibration capability or that the judge was too lenient on Step 1.

2. **High Calibrated rate (92.8%)**: The majority of responses explicitly stated evidence state (no significant difference, mixed evidence, etc.). This is notably high and warrants verification with human annotation.

3. **NO_DIFFERENCE and MIXED_EVIDENCE are the discriminative types**: These are where Pseudo-Precise (UCS=1) scores concentrate, suggesting models sometimes hedge but still lean directional.

4. **Model comparison**: DeepSeek and Qwen show very similar calibration patterns, with Qwen having slightly more Pseudo-Precise responses (9 vs 7).

5. **Next step**: Human annotation on 15-20 questions to validate LLM judge accuracy and establish inter-rater agreement.
