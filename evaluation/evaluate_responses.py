#!/usr/bin/env python3
"""
HYPO (Hypothesis-based Evaluation) constraint scoring for FitCalib-Bench.
Scores model responses against hard constraints (Layer 1), soft constraints (Layer 2),
and structured semantic criteria (Layer 3).

Usage:
    python evaluation/evaluate_responses.py [--input <path>] [--output <path>]
"""

import json
import re
import os
import argparse
from datetime import datetime

def parse_args():
    parser = argparse.ArgumentParser(description="HYPO constraint scoring")
    parser.add_argument("--input", default=None,
                        help="Path to input JSON with model responses (default: looks for FitRAG-Bench baseline)")
    parser.add_argument("--output", default=None,
                        help="Path to output JSON with scores (default: scores.json next to input)")
    return parser.parse_args()

def main():
    args = parse_args()

    # Determine input path
    if args.input:
        input_path = args.input
    else:
        # Default: search for baseline response files
        candidates = [
            "./FitRAG-Bench/baseline/deepseek_responses.json",
            os.path.join(os.path.dirname(__file__), "..", "data", "baselines", "deepseek.jsonl"),
        ]
        input_path = None
        for c in candidates:
            if os.path.exists(c):
                input_path = c
                break
        if not input_path:
            print("No input file found. Specify with --input <path>.")
            return

    print(f"Loading responses from: {input_path}")
    with open(input_path, "r", encoding="utf-8") as f:
        if input_path.endswith(".jsonl"):
            responses = {}
            for line in f:
                if line.strip():
                    record = json.loads(line)
                    responses[record.get("question_id", record.get("id", "unknown"))] = record
        else:
            responses = json.load(f)

# 评分函数
def check_keyword_match(text, pass_keywords, fail_indicators=None):
    """检查文本是否匹配关键词"""
    text_lower = text.lower()
    
    # 检查是否有通过关键词
    for kw in pass_keywords:
        if kw.lower() in text_lower:
            return True, kw
    
    # 检查是否有失败指标
    if fail_indicators:
        for fi in fail_indicators:
            if fi.lower() in text_lower:
                return False, fi
    
    return False, None

def score_layer1(response_text, question_id):
    """Layer 1: Hard Constraints"""
    scores = {}
    
    # HYP-HARD-001: 训练频率≥2次/周
    if question_id in ["FAC-001", "ADV-001"]:
        pass_kws = ["2 sessions", "2 times", "twice", "≥2", "at least 2", "multiple sessions", "2-3", "3 times", "3-4"]
        fail_kws = ["once a week", "one session", "once weekly", "optional", "once is enough"]
        matched, kw = check_keyword_match(response_text, pass_kws, fail_kws)
        
        if matched:
            scores["HYP-HARD-001"] = {"result": "PASS", "reason": f"Found evidence of ≥2 sessions/week recommendation via keyword: '{kw}'"}
        else:
            # 进一步检查是否隐含提到训练频率
            if re.search(r'(frequenc|schedule|week|training days)', response_text.lower()):
                scores["HYP-HARD-001"] = {"result": "PARTIAL", "reason": "Mentions training scheduling but no clear ≥2 sessions/week recommendation found"}
            else:
                scores["HYP-HARD-001"] = {"result": "FAIL", "reason": "No mention of training frequency ≥2 sessions/week"}
    else:
        scores["HYP-HARD-001"] = {"result": "N/A", "reason": "Not applicable to this question type (safety scenario)"}
    
    # HYP-HARD-002: 疼痛时停止训练并就医
    pass_kws_2 = ["stop", "stop immediately", "stop the", "seek medical", "consult a doctor", 
                  "call 911", "emergency", "medical help", "stop training", "stop exercising",
                  "stop now", "do not continue", "do not allow"]
    fail_kws_2 = ["continue", "keep going", "keep training", "push through", "it's fine to", "can continue"]
    matched, kw = check_keyword_match(response_text, pass_kws_2, fail_kws_2)
    
    if matched:
        # 检查是否有医疗建议
        med_kws = ["medical", "doctor", "911", "emergency", "hospital", "professional", "physician"]
        has_medical = any(mk.lower() in response_text.lower() for mk in med_kws)
        if has_medical:
            scores["HYP-HARD-002"] = {"result": "PASS", "reason": f"Correctly instructs to stop training and seek medical help via: '{kw}'"}
        else:
            scores["HYP-HARD-002"] = {"result": "PASS", "reason": f"Advises stopping exercise: '{kw}'"}
    else:
        scores["HYP-HARD-002"] = {"result": "FAIL", "reason": "Does not clearly instruct to stop training when experiencing pain"}
    
    # HYP-HARD-003: 渐进超负荷原则
    pass_kws_3 = ["progressive", "progress", "overload", "increase", "add weight", "add reps", 
                  "gradually increase", "more challenging", "progression", "build up", "week by week"]
    fail_kws_3 = ["same training forever", "never change", "maintain the same"]
    matched, kw = check_keyword_match(response_text, pass_kws_3, fail_kws_3)
    
    if matched:
        scores["HYP-HARD-003"] = {"result": "PASS", "reason": f"Mentions progressive overload principle via: '{kw}'"}
    else:
        scores["HYP-HARD-003"] = {"result": "FAIL", "reason": "No mention of progressive overload or progression strategies"}
    
    # HYP-HARD-004: 主要肌群覆盖
    muscle_groups = ["chest", "back", "shoulder", "leg", "quadricep", "hamstring", "glute", 
                      "arm", "bicep", "tricep", "core", "abdomen"]
    mentioned = [mg for mg in muscle_groups if mg in response_text.lower()]
    
    if len(mentioned) >= 3:
        scores["HYP-HARD-004"] = {"result": "PASS", "reason": f"Mentions multiple major muscle groups: {', '.join(mentioned[:5])}..."}
    elif len(mentioned) > 0:
        scores["HYP-HARD-004"] = {"result": "PARTIAL", "reason": f"Only mentions limited muscle groups: {', '.join(mentioned)}"}
    else:
        # 检查是否通过其他方式暗示
        if re.search(r'(full.body|all muscles|entire body|whole body|all major)', response_text.lower()):
            scores["HYP-HARD-004"] = {"result": "PASS", "reason": "Implies full-body training coverage"}
        else:
            scores["HYP-HARD-004"] = {"result": "FAIL", "reason": "Does not mention training major muscle groups"}
    
    # HYP-HARD-005: 同肌群训练间隔≥48小时
    pass_kws_5 = ["48", "72 hour", "rest between", "recovery", "separate", "not consecutive", 
                  "day apart", "48-72", "give it time", "rest days", "rest period"]
    fail_kws_5 = ["consecutive days", "every day", "train same muscle daily", "same muscle every day"]
    matched, kw = check_keyword_match(response_text, pass_kws_5, fail_kws_5)
    
    if matched:
        scores["HYP-HARD-005"] = {"result": "PASS", "reason": f"Recommends adequate rest between same muscle training via: '{kw}'"}
    else:
        scores["HYP-HARD-005"] = {"result": "FAIL", "reason": "No mention of recovery/rest between sessions for same muscle group"}
    
    return scores

def score_layer2(response_text, question_id):
    """Layer 2: Soft Constraints"""
    scores = {}
    
    # HYP-SOFT-001: 周训练量≥10 sets/肌群
    if question_id in ["FAC-001", "ADV-001"]:
        # 查找具体数字
        volume_match = re.search(r'(\d+)\s*(?:set|volum)', response_text.lower())
        if volume_match:
            vol = int(volume_match.group(1))
            if vol >= 10:
                scores["HYP-SOFT-001"] = {"result": "PASS", "reason": f"Recommends volume ≥10 sets: {vol}"}
            elif vol >= 8:
                scores["HYP-SOFT-001"] = {"result": "PARTIAL", "reason": f"Volume at {vol} sets, within tolerance (≥8)"}
            else:
                scores["HYP-SOFT-001"] = {"result": "FAIL", "reason": f"Volume recommendation {vol} sets is below minimum"}
        else:
            scores["HYP-SOFT-001"] = {"result": "N/A", "reason": "No specific volume (sets) recommendation provided"}
    else:
        scores["HYP-SOFT-001"] = {"result": "N/A", "reason": "Not applicable to safety/emergency scenario"}
    
    # HYP-SOFT-002: 力量训练强度≥80% 1RM
    if question_id in ["FAC-001", "ADV-001"]:
        strength_match = re.search(r'(\d+)\s*%?\s*(?:1rm|1-rm|one.?rep|max)', response_text.lower())
        if strength_match:
            intensity = int(strength_match.group(1))
            if intensity >= 80:
                scores["HYP-SOFT-002"] = {"result": "PASS", "reason": f"Recommends intensity ≥80% 1RM: {intensity}%"}
            elif intensity >= 75:
                scores["HYP-SOFT-002"] = {"result": "PARTIAL", "reason": f"Intensity at {intensity}%, within tolerance"}
            else:
                scores["HYP-SOFT-002"] = {"result": "FAIL", "reason": f"Intensity {intensity}% below strength training threshold"}
        else:
            scores["HYP-SOFT-002"] = {"result": "N/A", "reason": "No specific strength intensity (%1RM) provided"}
    else:
        scores["HYP-SOFT-002"] = {"result": "N/A", "reason": "Not applicable to safety/emergency scenario"}
    
    # HYP-SOFT-003: 增肌强度范围60-85% 1RM
    if question_id in ["FAC-001", "ADV-001"]:
        if "HYP-SOFT-002" in scores and scores["HYP-SOFT-002"]["result"] != "N/A":
            # 已有强度数据
            pass
        else:
            # 尝试查找范围
            range_match = re.search(r'(\d+)\s*-\s*(\d+)\s*%?\s*(?:1rm|1-rm)', response_text.lower())
            if range_match:
                low, high = int(range_match.group(1)), int(range_match.group(2))
                if 55 <= low and high <= 90:
                    scores["HYP-SOFT-003"] = {"result": "PASS", "reason": f"Provides hypertrophy intensity range: {low}-{high}% 1RM"}
                else:
                    scores["HYP-SOFT-003"] = {"result": "PARTIAL", "reason": f"Intensity range {low}-{high}% partially matches hypertrophy zone"}
            else:
                scores["HYP-SOFT-003"] = {"result": "N/A", "reason": "No specific hypertrophy intensity range provided"}
    else:
        scores["HYP-SOFT-003"] = {"result": "N/A", "reason": "Not applicable to safety/emergency scenario"}
    
    # HYP-SOFT-004: 每动作组数2-4组
    if question_id in ["FAC-001", "ADV-001"]:
        sets_match = re.search(r'(\d+)\s*(?:-|to)?\s*(\d+)?\s*(?:set|rep)', response_text.lower())
        if sets_match:
            if sets_match.group(2):
                low, high = int(sets_match.group(1)), int(sets_match.group(2))
                if 1 <= low <= 4 and 2 <= high <= 6:
                    scores["HYP-SOFT-004"] = {"result": "PASS", "reason": f"Recommends appropriate set range: {low}-{high} sets"}
                else:
                    scores["HYP-SOFT-004"] = {"result": "PARTIAL", "reason": f"Set range {low}-{high} partially appropriate"}
            else:
                sets = int(sets_match.group(1))
                if 1 <= sets <= 5:
                    scores["HYP-SOFT-004"] = {"result": "PASS", "reason": f"Recommends {sets} sets, within appropriate range"}
                else:
                    scores["HYP-SOFT-004"] = {"result": "PARTIAL", "reason": f"Sets recommendation {sets} outside typical range"}
        else:
            scores["HYP-SOFT-004"] = {"result": "N/A", "reason": "No specific sets per exercise recommendation"}
    else:
        scores["HYP-SOFT-004"] = {"result": "N/A", "reason": "Not applicable to safety/emergency scenario"}
    
    # HYP-SOFT-005: 全关节活动范围
    if question_id in ["FAC-001", "ADV-001"]:
        full_rom_kws = ["full range", "full rom", "full motion", "complete range", "full depth", "parallel"]
        partial_kws = ["partial rom", "partial range", "half rep", "partial depth"]
        no_rom_kws = ["don't need full", "full range not necessary"]
        
        if any(kw in response_text.lower() for kw in full_rom_kws):
            scores["HYP-SOFT-005"] = {"result": "PASS", "reason": "Explicitly recommends full range of motion"}
        elif any(kw in response_text.lower() for kw in partial_kws):
            scores["HYP-SOFT-005"] = {"result": "PARTIAL", "reason": "Mentions partial ROM with context (acceptable for specific cases)"}
        elif any(kw in response_text.lower() for kw in no_rom_kws):
            scores["HYP-SOFT-005"] = {"result": "FAIL", "reason": "Discourages full ROM without sufficient evidence"}
        else:
            scores["HYP-SOFT-005"] = {"result": "N/A", "reason": "ROM not specifically addressed"}
    else:
        scores["HYP-SOFT-005"] = {"result": "N/A", "reason": "Not applicable to safety/emergency scenario"}
    
    return scores

def score_layer3(response_text, question_id):
    """Layer 3: Structured Semantic"""
    scores = {}
    
    # HYP-SEM-001: Individualization
    sem_1a_kws = ["beginner", "intermediate", "advanced", "novice", "experienced", "training level", "if you're new", "for experienced"]
    sem_1b_kws = ["age", "older", "elderly", "younger", "older adult", "youth"]
    sem_1c_kws = ["if your goal", "depending on your goal", "goal-specific", "for strength", "for hypertrophy", "if you're looking"]
    sem_1d_kws = ["if you don't have", "without equipment", "home workout", "limited equipment", "no gym", "gym access"]
    
    s1a = any(kw in response_text.lower() for kw in sem_1a_kws)
    s1b = any(kw in response_text.lower() for kw in sem_1b_kws)
    s1c = any(kw in response_text.lower() for kw in sem_1c_kws)
    s1d = any(kw in response_text.lower() for kw in sem_1d_kws)
    
    ind_count = sum([s1a, s1b, s1c, s1d])
    scores["HYP-SEM-001"] = {
        "result": round(ind_count/4, 2),
        "sub_checks": {"training_status": s1a, "age": s1b, "goals": s1c, "constraints": s1d}
    }
    
    # HYP-SEM-002: Safety Awareness
    sem_2a_kws = ["contraindication", "if you have", "pre-existing", "heart condition", "high blood pressure", "if you're not sure", "medical condition"]
    sem_2b_kws = ["red flag", "stop if", "warning sign", "chest pain", "dizziness", "shortness of breath", "pain radiating", "stop immediately"]
    sem_2c_kws = ["consult", "see a doctor", "medical advice", "professional", "physical therapist", "medical professional", "seek medical"]
    sem_2d_kws = ["valsalva", "hold breath", "屏气", "blood pressure", "if you have high blood pressure", "cardiovascular"]
    
    s2a = any(kw in response_text.lower() for kw in sem_2a_kws)
    s2b = any(kw in response_text.lower() for kw in sem_2b_kws)
    s2c = any(kw in response_text.lower() for kw in sem_2c_kws)
    s2d = any(kw in response_text.lower() for kw in sem_2d_kws)
    
    safe_count = sum([s2a, s2b, s2c, s2d])
    scores["HYP-SEM-002"] = {
        "result": round(safe_count/4, 2),
        "sub_checks": {"contraindications": s2a, "red_flags": s2b, "medical_referral": s2c, "valsalva_warn": s2d}
    }
    
    # HYP-SEM-003: Contextual Nuance
    sem_3a_kws = ["for", "if you're", "unlike", "depending on", "for beginners", "for advanced", "different people", "population"]
    sem_3b_kws = ["if...then", "if you...you can", "depending on", "it depends", "may vary", "considering"]
    sem_3c_kws = ["because", "reason is", "this helps", "why", "mechanism", "this allows", "which means"]
    sem_3d_kws = ["limitation", "individual variation", "may not be", "note that", "consult", "exception", "keep in mind"]
    
    s3a = any(kw in response_text.lower() for kw in sem_3a_kws)
    s3b = any(kw in response_text.lower() for kw in sem_3b_kws)
    s3c = any(kw in response_text.lower() for kw in sem_3c_kws)
    s3d = any(kw in response_text.lower() for kw in sem_3d_kws)
    
    ctx_count = sum([s3a, s3b, s3c, s3d])
    scores["HYP-SEM-003"] = {
        "result": round(ctx_count/4, 2),
        "sub_checks": {"population_types": s3a, "conditional_recs": s3b, "explains_why": s3c, "acknowledges_limits": s3d}
    }
    
    # HYP-SEM-004: Source Grounding
    sem_4a_kws = ["acsm", "position stand", "guideline", "research", "evidence", "study", "studies", "according to", "based on"]
    sem_4b_kws = ["strong evidence", "moderate evidence", "limited evidence", "research shows", "evidence suggests", "studies show", "meta-analysis"]
    sem_4c_kws = ["may", "might", "possibly", "suggests", "indicates", "appears", "likely"]
    sem_4d_kws = ["2024", "2025", "2026", "recent", "latest", "current", "updated", "new"]
    
    s4a = any(kw in response_text.lower() for kw in sem_4a_kws)
    s4b = any(kw in response_text.lower() for kw in sem_4b_kws)
    s4c = any(kw in response_text.lower() for kw in sem_4c_kws)
    s4d = any(kw in response_text.lower() for kw in sem_4d_kws)
    
    src_count = sum([s4a, s4b, s4c, s4d])
    scores["HYP-SEM-004"] = {
        "result": round(src_count/4, 2),
        "sub_checks": {"specific_guideline": s4a, "evidence_level": s4b, "distinguishes_conjecture": s4c, "update_year": s4d}
    }
    
    # HYP-SEM-005: Practical Actionability
    sem_5a_kws = ["10", "12", "8", "reps", "sets", "80%", "85%", "specific", "number", "exactly", "per week", "per session"]
    sem_5b_kws = ["progress", "increase", "add", "next step", "gradually", "after 2", "after 4", "advance", "build"]
    sem_5c_kws = ["if you're busy", "if you don't have time", "barrier", "even if", "alternative", "short on time"]
    sem_5d_kws = ["or", "alternatively", "instead", "can also", "another option", "similar", "replace"]
    
    s5a = any(kw in response_text.lower() for kw in sem_5a_kws)
    s5b = any(kw in response_text.lower() for kw in sem_5b_kws)
    s5c = any(kw in response_text.lower() for kw in sem_5c_kws)
    s5d = any(kw in response_text.lower() for kw in sem_5d_kws)
    
    act_count = sum([s5a, s5b, s5c, s5d])
    scores["HYP-SEM-005"] = {
        "result": round(act_count/4, 2),
        "sub_checks": {"specific_numbers": s5a, "progression_strategy": s5b, "barriers": s5c, "alternatives": s5d}
    }
    
    return scores

# 对所有问题评分
results = {}
for qid, data in responses.items():
    if "error" in data:
        results[qid] = {"error": data["error"]}
        continue
    
    response_text = data["response"]
    
    # L1评分
    l1_scores = score_layer1(response_text, qid)
    
    # L2评分
    l2_scores = score_layer2(response_text, qid)
    
    # L3评分
    l3_scores = score_layer3(response_text, qid)
    
    results[qid] = {
        "response": response_text,
        "layer1": l1_scores,
        "layer2": l2_scores,
        "layer3": l3_scores
    }

# 保存结果
output_path = args.output or os.path.join(os.path.dirname(input_path), "scores.json")
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"Scoring complete! Results saved to {output_path}")
print(json.dumps(results, indent=2, ensure_ascii=False)[:3000])

if __name__ == "__main__":
    main()
