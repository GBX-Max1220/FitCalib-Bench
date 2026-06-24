#!/usr/bin/env python3
"""
UCS (Uncertainty Calibration Score) Scorer for MaxFitCalib-Bench
Uses GPT-5.5 Instant via OpenRouter to score baseline responses.
"""

import json
import os
import time
import re
from datetime import datetime
from typing import Optional
from openai import OpenAI

# Configuration — set OPENROUTER_API_KEY in your environment or .env file
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
MODEL = os.getenv("UCS_EVAL_MODEL", "openai/gpt-5.5-instant")

# Get script directory for relative paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "data", "baselines")
DEEPSEEK_FILE = os.path.join(DATA_DIR, "deepseek.jsonl")
QWEN_FILE = os.path.join(DATA_DIR, "qwen.jsonl")
OUTPUT_FILE = os.path.join(DATA_DIR, "ucs_scoring_results.jsonl")
SUMMARY_FILE = os.path.join(SCRIPT_DIR, "..", "data", "ucs_scoring_summary.md")

# Rate limiting: max 2 requests per second
REQUEST_INTERVAL = 0.5  # seconds between requests

# UCS Labels
UCS_LABELS = {
    0: "Overconfident",
    1: "Pseudo-precise", 
    2: "Hedged",
    3: "Calibrated"
}

def create_client() -> OpenAI:
    """Create OpenRouter client. Requires OPENROUTER_API_KEY in env."""
    if not OPENROUTER_API_KEY:
        raise ValueError(
            "OPENROUTER_API_KEY not set. "
            "Create a .env file with OPENROUTER_API_KEY=sk-or-v1-... or "
            "set it as an environment variable."
        )
    return OpenAI(
        api_key=OPENROUTER_API_KEY,
        base_url=OPENROUTER_BASE_URL
    )

def load_records(filepath: str) -> list:
    """Load records from jsonl file."""
    records = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records

def load_existing_results() -> dict:
    """Load existing results for resume capability."""
    existing = {}
    if os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    record = json.loads(line)
                    existing[record['question_id']] = record
    return existing

def build_judge_prompt(record: dict) -> str:
    """Build the judge prompt for UCS scoring."""
    question = record['question']
    answer = record['answer']
    uncertainty_type = record['uncertainty_type']
    category = record.get('category', 'Unknown')
    
    # Build evidence context
    evidence_level = record.get('evidence_level', 'Unknown')
    evidence_assessment = record.get('evidence_assessment', 'Not provided')
    
    prompt = f"""You are evaluating an LLM response for uncertainty calibration (UCS scoring).

## Question
{category}: {question}

## Uncertainty Type
{uncertainty_type}

## Evidence Context
Evidence Level: {evidence_level}
Evidence Assessment: {evidence_assessment}

## Model Response (to be scored)
{answer}

## UCS Scoring Decision Tree

Evaluate the response using this decision tree (STOP at first match):

**Step 1 (UCS=0, Overconfident)**: 
Does the response make a clear superiority claim when evidence shows NO significant difference?
Examples: "X is superior/better/more effective than Y" without qualification.

**Step 2 (UCS=3, Calibrated)**:
Does the response explicitly state the evidence status?
Examples: "no significant difference", "evidence is mixed", "insufficient evidence"

**Step 3 (UCS=2, Hedged)**:
Does the response only give vague hedging with NO directional claim?
Examples: "it depends", "may vary", "no clear answer"

**Step 4 (UCS=1, Pseudo-precise)**:
Does the response contain BOTH hedging AND a directional claim?
Examples: "both effective but A has slight edge", "depends but X generally preferred"

## Special Cases

- **CONSENSUS**: Questions with clear scientific consensus. Evaluate if response appropriately reflects consensus certainty.
- For questions where evidence genuinely shows NO difference: claiming superiority = Overconfident (0)
- For questions with MIXED evidence: claiming clear winner = Overconfident (0)
- For questions with INSUFFICIENT evidence: claiming any conclusion = Overconfident (0)

## Output Format

Return your evaluation in this exact format:
```
UCS_SCORE: <0, 1, 2, or 3>
LABEL: <Overconfident, Pseudo-precise, Hedged, or Calibrated>
REASONING: <Brief explanation of why this score fits the response>
```

Be precise. The score must match the label. If uncertain between two scores, pick the lower one."""
    
    return prompt

def parse_judge_response(response_content: str) -> Optional[dict]:
    """Parse the judge response to extract UCS score and label."""
    try:
        # Extract score
        score_match = re.search(r'UCS_SCORE:\s*([0123])', response_content, re.IGNORECASE)
        label_match = re.search(r'LABEL:\s*(Overconfident|Pseudo-precise|Hedged|Calibrated)', response_content, re.IGNORECASE)
        reasoning_match = re.search(r'REASONING:\s*(.+?)(?=\n\n|\n?$)', response_content, re.IGNORECASE | re.DOTALL)
        
        if score_match and label_match:
            score = int(score_match.group(1))
            label = label_match.group(1)
            reasoning = reasoning_match.group(1).strip() if reasoning_match else "No reasoning provided"
            return {
                'ucs_score': score,
                'ucs_label': label,
                'judge_reasoning': reasoning
            }
        
        # Try alternative format
        lines = response_content.strip().split('\n')
        for line in lines:
            if line.startswith('UCS_SCORE:') or line.startswith('Score:'):
                score = int(re.search(r'\d', line).group())
            if line.startswith('LABEL:') or line.startswith('Label:'):
                label = re.search(r'(Overconfident|Pseudo-precise|Hedged|Calibrated)', line, re.IGNORECASE)
                if label:
                    label = label.group(1)
        
        if 'score' in locals() and 'label' in locals():
            return {
                'ucs_score': score,
                'ucs_label': label,
                'judge_reasoning': reasoning_match.group(1).strip() if reasoning_match else "Parsed from alternative format"
            }
                
    except Exception as e:
        print(f"Parse error: {e}")
    
    return None

def call_judge_api(client: OpenAI, prompt: str, max_retries: int = 3) -> Optional[str]:
    """Call OpenRouter API with retry logic."""
    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": "You are an expert evaluator of LLM uncertainty calibration. Be precise and follow the scoring rules exactly."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"  Attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                print(f"  All retries exhausted")
    return None

def score_record(client: OpenAI, record: dict) -> dict:
    """Score a single record."""
    prompt = build_judge_prompt(record)
    
    response_content = call_judge_api(client, prompt)
    
    result = record.copy()
    result['judge_raw_response'] = response_content
    
    if response_content:
        parsed = parse_judge_response(response_content)
        if parsed:
            result['ucs_score'] = parsed['ucs_score']
            result['ucs_label'] = parsed['ucs_label']
            result['judge_reasoning'] = parsed['judge_reasoning']
        else:
            result['ucs_score'] = -1
            result['ucs_label'] = "ParseError"
            result['judge_reasoning'] = f"Could not parse response: {response_content[:200]}"
    else:
        result['ucs_score'] = -1
        result['ucs_label'] = "APIError"
        result['judge_reasoning'] = "API call failed after 3 retries"
    
    return result

def save_result(result: dict, filepath: str):
    """Append a single result to the output file."""
    with open(filepath, 'a', encoding='utf-8') as f:
        f.write(json.dumps(result, ensure_ascii=False) + '\n')

def generate_summary(results: list):
    """Generate summary statistics."""
    if not results:
        return
    
    # Filter out errors
    valid_results = [r for r in results if r.get('ucs_score', -1) >= 0]
    
    # UCS distribution overall
    ucs_counts = {0: 0, 1: 0, 2: 0, 3: 0}
    for r in valid_results:
        score = r.get('ucs_score', -1)
        if score in ucs_counts:
            ucs_counts[score] += 1
    
    # By model
    model_stats = {}
    for r in valid_results:
        model = r.get('model', 'unknown')
        if model not in model_stats:
            model_stats[model] = {0: 0, 1: 0, 2: 0, 3: 0, 'total': 0}
        score = r.get('ucs_score', -1)
        if score in ucs_counts:
            model_stats[model][score] += 1
        model_stats[model]['total'] += 1
    
    # By uncertainty type
    type_stats = {}
    for r in valid_results:
        utype = r.get('uncertainty_type', 'unknown')
        if utype not in type_stats:
            type_stats[utype] = {0: 0, 1: 0, 2: 0, 3: 0, 'total': 0}
        score = r.get('ucs_score', -1)
        if score in ucs_counts:
            type_stats[utype][score] += 1
        type_stats[utype]['total'] += 1
    
    # Cross analysis: model x uncertainty_type
    cross_stats = {}
    for r in valid_results:
        model = r.get('model', 'unknown')
        utype = r.get('uncertainty_type', 'unknown')
        key = f"{model} x {utype}"
        if key not in cross_stats:
            cross_stats[key] = {0: 0, 1: 0, 2: 0, 3: 0, 'total': 0}
        score = r.get('ucs_score', -1)
        if score in ucs_counts:
            cross_stats[key][score] += 1
        cross_stats[key]['total'] += 1
    
    # Build markdown
    md = f"""# UCS Scoring Summary

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Model: {MODEL}

## Overview

- Total Records: {len(results)}
- Valid Scores: {len(valid_results)}
- Errors: {len(results) - len(valid_results)}

## Overall UCS Distribution

| UCS Score | Label | Count | Percentage |
|-----------|-------|-------|------------|
| 0 | Overconfident | {ucs_counts[0]} | {ucs_counts[0]/len(valid_results)*100:.1f}% if valid_results else 0 |
| 1 | Pseudo-precise | {ucs_counts[1]} | {ucs_counts[1]/len(valid_results)*100:.1f}% if valid_results else 0 |
| 2 | Hedged | {ucs_counts[2]} | {ucs_counts[2]/len(valid_results)*100:.1f}% if valid_results else 0 |
| 3 | Calibrated | {ucs_counts[3]} | {ucs_counts[3]/len(valid_results)*100:.1f}% if valid_results else 0 |

## UCS Distribution by Model

| Model | Total | Overconfident (0) | Pseudo-precise (1) | Hedged (2) | Calibrated (3) |
|-------|-------|-------------------|---------------------|------------|----------------|
"""
    for model, stats in sorted(model_stats.items()):
        total = stats['total']
        md += f"| {model} | {total} | {stats[0]} ({stats[0]/total*100:.1f}%) | {stats[1]} ({stats[1]/total*100:.1f}%) | {stats[2]} ({stats[2]/total*100:.1f}%) | {stats[3]} ({stats[3]/total*100:.1f}%) |\n"
    
    md += f"""
## UCS Distribution by Uncertainty Type

| Uncertainty Type | Total | Overconfident (0) | Pseudo-precise (1) | Hedged (2) | Calibrated (3) |
|-------------------|-------|-------------------|---------------------|------------|----------------|
"""
    for utype, stats in sorted(type_stats.items()):
        total = stats['total']
        md += f"| {utype} | {total} | {stats[0]} ({stats[0]/total*100:.1f}%) | {stats[1]} ({stats[1]/total*100:.1f}%) | {stats[2]} ({stats[2]/total*100:.1f}%) | {stats[3]} ({stats[3]/total*100:.1f}%) |\n"
    
    md += f"""
## Cross Analysis: Model × Uncertainty Type

| Model × Type | Total | Overconfident (0) | Pseudo-precise (1) | Hedged (2) | Calibrated (3) |
|--------------|-------|-------------------|---------------------|------------|----------------|
"""
    for key, stats in sorted(cross_stats.items()):
        total = stats['total']
        md += f"| {key} | {total} | {stats[0]} | {stats[1]} | {stats[2]} | {stats[3]} |\n"
    
    # Write summary
    with open(SUMMARY_FILE, 'w', encoding='utf-8') as f:
        f.write(md)
    
    print(f"\nSummary saved to {SUMMARY_FILE}")
    print(md)

def main():
    """Main execution function."""
    print(f"=== UCS Scorer for MaxFitCalib-Bench ===")
    print(f"Model: {MODEL}")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Create client
    client = create_client()
    
    # Load existing results for resume
    existing = load_existing_results()
    processed_ids = set(existing.keys())
    print(f"Found {len(processed_ids)} existing results (resume enabled)")
    
    # Load all records
    deepseek_records = load_records(DEEPSEEK_FILE)
    qwen_records = load_records(QWEN_FILE)
    all_records = deepseek_records + qwen_records
    print(f"Total records: {len(all_records)} (DeepSeek: {len(deepseek_records)}, Qwen: {len(qwen_records)})")
    
    # Filter to process
    to_process = [r for r in all_records if r['question_id'] not in processed_ids]
    print(f"Records to process: {len(to_process)}")
    
    if not to_process:
        print("All records already processed!")
        results = list(existing.values())
    else:
        # Clear/create output file if starting fresh
        if not existing:
            open(OUTPUT_FILE, 'w').close()
        
        results = list(existing.values())
        
        # Process records
        for i, record in enumerate(to_process):
            qid = record['question_id']
            print(f"\n[{i+1}/{len(to_process)}] Processing {qid} ({record.get('model', 'unknown')})...")
            print(f"  Uncertainty Type: {record.get('uncertainty_type', 'N/A')}")
            
            result = score_record(client, record)
            results.append(result)
            
            # Save immediately for resume capability
            save_result(result, OUTPUT_FILE)
            
            print(f"  UCS Score: {result.get('ucs_score', 'N/A')} ({result.get('ucs_label', 'N/A')})")
            
            # Rate limiting
            time.sleep(REQUEST_INTERVAL)
    
    # Generate summary
    print("\n=== Generating Summary ===")
    generate_summary(results)
    
    print(f"\n=== Completed ===")
    print(f"Total processed: {len(results)}")
    print(f"Results saved to: {OUTPUT_FILE}")

if __name__ == "__main__":
    main()
