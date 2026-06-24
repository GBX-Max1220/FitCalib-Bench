#!/usr/bin/env python3
"""
Multi-provider LLM caller for FitCalib-Bench.
Reads questions, calls configured provider, saves responses.

Usage:
    # Set your API key in .env (see .env.example)
    python evaluation/call_model.py --provider deepseek --input data/questions/ --output results.jsonl

Supported providers: deepseek, qwen, openai
"""

import json
import os
import time
import argparse
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env from project root
load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

PROVIDER_CONFIGS = {
    "deepseek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
        "env_key": "DEEPSEEK_API_KEY",
    },
    "qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "env_key": "QWEN_API_KEY",
    },
    "openai": {
        "base_url": "https://api.openai.com/v1",
        "model": "gpt-4o-mini",
        "env_key": "OPENAI_API_KEY",
    },
}

SYSTEM_PROMPT = (
    "You are a fitness professional answering a client's question. "
    "Provide a detailed, practical response based on your knowledge."
)


def load_questions(input_path: str) -> list[dict]:
    """Load questions from a directory of JSON files or a single JSONL file."""
    questions = []
    p = Path(input_path)

    if p.is_dir():
        for f in sorted(p.glob("*.json")):
            with open(f, encoding="utf-8") as fh:
                data = json.load(fh)
                # Support both list and single-object formats
                if isinstance(data, list):
                    questions.extend(data)
                else:
                    questions.append(data)
    elif p.suffix == ".jsonl":
        with open(p, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    questions.append(json.loads(line))
    elif p.suffix == ".json":
        with open(p, encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, list):
                questions.extend(data)
            else:
                questions.append(data)
    else:
        raise ValueError(f"Unsupported input format: {p.suffix}")

    return questions


def call_provider(provider: str, question: str, temperature: float = 0.7) -> Optional[str]:
    """Call a single provider and return the response text."""
    import requests

    config = PROVIDER_CONFIGS.get(provider)
    if not config:
        raise ValueError(f"Unknown provider: {provider}. Supported: {list(PROVIDER_CONFIGS.keys())}")

    api_key = os.getenv(config["env_key"])
    if not api_key:
        raise ValueError(
            f"{config['env_key']} not set. "
            f"Add it to .env: {config['env_key']}=sk-..."
        )

    prompt = f"{SYSTEM_PROMPT}\n\nQuestion: {question}\n\nPlease provide your best answer."

    payload = {
        "model": config["model"],
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
    }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        resp = requests.post(
            f"{config['base_url']}/chat/completions",
            headers=headers,
            json=payload,
            timeout=60,
        )
        resp.raise_for_status()
        result = resp.json()
        return result["choices"][0]["message"]["content"]
    except Exception as e:
        return None  # Caller handles logging


def main():
    parser = argparse.ArgumentParser(description="Multi-provider LLM caller")
    parser.add_argument("--provider", choices=list(PROVIDER_CONFIGS.keys()), required=True,
                        help="LLM provider to call")
    parser.add_argument("--input", required=True,
                        help="Path to questions (directory of JSONs, single JSON, or JSONL)")
    parser.add_argument("--output", required=True,
                        help="Output JSONL path")
    parser.add_argument("--rate-limit", type=float, default=1.0,
                        help="Seconds between requests (default: 1.0)")
    args = parser.parse_args()

    questions = load_questions(args.input)
    print(f"Loaded {len(questions)} questions from {args.input}")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    succeeded = 0
    failed = 0

    for i, q in enumerate(questions):
        qid = q.get("id", q.get("question_id", f"q_{i:04d}"))
        question_text = q.get("question", q.get("text", ""))
        if not question_text:
            print(f"  [{i+1}/{len(questions)}] {qid}: SKIP (no question text)")
            continue

        print(f"  [{i+1}/{len(questions)}] {qid} ({args.provider})...", end=" ", flush=True)
        response = call_provider(args.provider, question_text)

        record = {
            "question_id": qid,
            "question": question_text,
            "model": args.provider,
            "category": q.get("category", q.get("uncertainty_type", "")),
        }

        if response:
            record["response"] = response
            succeeded += 1
            print(f"OK ({len(response)} chars)")
        else:
            record["error"] = "API call failed"
            failed += 1
            print("FAILED")

        with open(output_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

        if i < len(questions) - 1:
            time.sleep(args.rate_limit)

    print(f"\nDone. {succeeded} succeeded, {failed} failed.")
    print(f"Results saved to {output_path}")


if __name__ == "__main__":
    main()
