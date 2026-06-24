# MaxFitCalib-Bench Full Baseline Evaluation Report

**Generated**: 2026-05-14 04:31:54  
**Total Questions**: 126  
**Models Evaluated**: DeepSeek V4, Qwen Plus

---

## 1. Overview

| Metric | DeepSeek V4 | Qwen Plus |
|--------|-------------|-----------|
| Total Questions | 126 | 126 |
| JSON Parse Success | 95 | 124 |
| Parse Rate | 75.4% | 98.41% |
| Valid Confidence Scores | 95 | 124 |
| **Average Confidence** | **91.16** | **93.72** |

---

## 2. Confidence Distribution by Uncertainty Type

### DeepSeek V4
| Uncertainty Type | Count | Avg Confidence |
|-------------------|-------|----------------|
| CONSENSUS | 52 | 93.1 |
| EVOLVING | 17 | 89.1 |
| INSUFFICIENT_EVIDENCE | 3 | 87.3 |
| MIXED_EVIDENCE | 15 | 89.0 |
| NO_DIFFERENCE | 8 | 88.1 |

### Qwen Plus
| Uncertainty Type | Count | Avg Confidence |
|-------------------|-------|----------------|
| CONSENSUS | 69 | 94.9 |
| EVOLVING | 20 | 92.8 |
| INSUFFICIENT_EVIDENCE | 4 | 86.8 |
| MIXED_EVIDENCE | 21 | 93.2 |
| NO_DIFFERENCE | 10 | 91.1 |

---

## 3. Confidence Distribution by Category

### DeepSeek V4
| Category | Count | Avg Confidence |
|----------|-------|----------------|
| adversarial | 15 | 89.3 |
| boundary | 11 | 92.5 |
| factual | 27 | 92.3 |
| psychology | 8 | 88.1 |
| recency | 7 | 91.4 |
| recovery | 7 | 91.4 |
| safety | 5 | 89.0 |
| scenario | 15 | 92.0 |

### Qwen Plus
| Category | Count | Avg Confidence |
|----------|-------|----------------|
| adversarial | 20 | 92.7 |
| boundary | 15 | 94.5 |
| factual | 37 | 93.9 |
| psychology | 8 | 92.6 |
| recency | 8 | 95.0 |
| recovery | 9 | 93.2 |
| safety | 6 | 91.2 |
| scenario | 21 | 94.7 |

---

## 4. Confidence Histogram (10-point bins)

### DeepSeek V4
| Range | Distribution | Count |
|-------|--------------|-------|
|   0- 10 |                           | 0 |
|  10- 20 |                           | 0 |
|  20- 30 |                           | 0 |
|  30- 40 |                           | 0 |
|  40- 50 |                           | 0 |
|  50- 60 |                           | 0 |
|  60- 70 |                           | 0 |
|  70- 80 |                           | 1 |
|  80- 90 | ███████████               | 22 |
|  90-100 | ███████████████████████████████████ | 71 |

### Qwen Plus
| Range | Distribution | Count |
|-------|--------------|-------|
|   0- 10 |                           | 0 |
|  10- 20 |                           | 0 |
|  20- 30 |                           | 0 |
|  30- 40 |                           | 0 |
|  40- 50 |                           | 1 |
|  50- 60 |                           | 0 |
|  60- 70 |                           | 0 |
|  70- 80 |                           | 1 |
|  80- 90 | ████                      | 9 |
|  90-100 | █████████████████████████████████████████████████████ | 107 |

---

## 5. Sample Responses

### DeepSeek V4 - Sample (first 3)

**ADV-001** (adversarial)
- Confidence: 95
- Evidence Assessment: This is a well-researched topic with strong evidence from biomechanical studies and systematic revie...
- Answer: No, this is not true. The idea that the knees should never pass the toes during a squat is a common myth that lacks scientific support. In fact, restricting the knees from moving forward over the toes...


**ADV-002** (adversarial)
- Confidence: 85
- Evidence Assessment: Moderate-quality evidence from clinical practice guidelines and expert consensus (e.g., from the Nor...
- Answer: No, individuals with lumbar disc herniation do not necessarily need to avoid deadlifts completely, but they should approach this exercise with caution and under professional guidance. The key factors ...


**ADV-003** (adversarial)
- Confidence: 95
- Evidence Assessment: Strong consensus from exercise physiology research and sports science literature. Multiple studies o...
- Answer: No, resistance training will not make most women look 'bulky' or overly muscular. This is a common misconception. The physiological reality is that women have significantly lower levels of testosteron...


### Qwen Plus - Sample (first 3)

**ADV-001** (adversarial)
- Confidence: 95
- Evidence Assessment: High-quality biomechanical research (e.g., Fry et al., 2003, JSCR; Caterisano et al., 2002, JOSPT) c...
- Answer: No, it is not true that the knees should never pass the toes during squatting to prevent knee injuries. This is a persistent myth with no scientific support. Biomechanical research shows that restrict...


**ADV-002** (adversarial)
- Confidence: 92
- Evidence Assessment: Moderate-to-high quality evidence from clinical guidelines (e.g., APTA, NICE), systematic reviews (e...
- Answer: Individuals with lumbar disc herniation should not universally avoid deadlifts completely, but their inclusion must be highly individualized, phase-dependent, and guided by clinical assessment. During...


**ADV-003** (adversarial)
- Confidence: 95
- Evidence Assessment: High-quality evidence from longitudinal resistance training studies, hormonal physiology research, a...
- Answer: No, resistance training will not make most women look 'bulky' or excessively muscular. Women typically have much lower circulating testosterone—averaging 15–70 ng/dL compared to men's 250–1100 ng/dL—w...


---

## 6. Key Findings

1. **Confidence Calibration**: Both models show high average confidence (>90%), suggesting potential overconfidence
2. **Parse Success**: Qwen (92.5%) outperforms DeepSeek (75.4%) in JSON parsing
3. **Model Comparison**: 
   - DeepSeek: avg 91.16, 95 parse success
   - Qwen: avg 93.72, 124 parse success

---

## 7. Notes

- API delay: 1s between calls
- Max tokens: 1500
- Temperature: 0.7
- Scoring not yet applied (to be done separately)

---

*Report generated by MaxFitCalib-Bench Evaluation Suite*
