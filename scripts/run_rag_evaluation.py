#!/usr/bin/env python3
"""Runs the 10 required RAG evaluation questions and writes raw results to JSON.

Covers direct factual questions, questions spanning multiple policy documents/sections,
deliberately ambiguous questions, and questions with no answer in the documents. The
correctness judgment and observed-limitations write-up (which require human review of
the actual answers) live in reports/rag_evaluation_results.md, authored after inspecting
this script's JSON output.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from src.common.config import get_paths
from src.rag.pipeline import answer_question

EVALUATION_QUESTIONS = [
    {
        "id": "Q1", "category": "direct_factual",
        "question": "What is the maximum DTI allowed for a conventional loan?",
        "expected_answer": "45%, up to 50% with compensating factors (6+ months reserves, credit score >= 720, or LTV below 75%).",
    },
    {
        "id": "Q2", "category": "direct_factual",
        "question": "What is the maximum LTV for an FHA loan?",
        "expected_answer": "96.5% LTV with a minimum 580 credit score; 90% LTV for scores between 500-579.",
    },
    {
        "id": "Q3", "category": "direct_factual",
        "question": "How long are denied application files retained?",
        "expected_answer": "25 months from the date of the adverse-action notice.",
    },
    {
        "id": "Q4", "category": "direct_factual",
        "question": "Which credit score tier requires manual underwriting review for conventional loans?",
        "expected_answer": "Tier 4 (660-699 credit score).",
    },
    {
        "id": "Q5", "category": "cross_section",
        "question": "If a Texas home-equity loan exceeds the state's LTV cap, is that automatically considered high-risk under the high-risk criteria policy?",
        "expected_answer": (
            "Texas caps Section 50(a)(6) home-equity loans at 80% LTV (state overlay policy). "
            "The high-risk criteria policy separately flags any loan at/above 95% LTV as high-risk. "
            "So exceeding the 80% Texas cap alone does not automatically trigger the 95% high-risk threshold — "
            "these are two distinct, not automatically linked, rules."
        ),
    },
    {
        "id": "Q6", "category": "cross_section",
        "question": "What happens when a borrower has a credit score below 620 and a DTI above 40%?",
        "expected_answer": (
            "Manual underwriting is required regardless of loan type or automated-underwriting-system "
            "recommendation (credit score tier policy, Section 2)."
        ),
    },
    {
        "id": "Q7", "category": "ambiguous",
        "question": "What's the limit?",
        "expected_answer": (
            "Ambiguous — the documents define several different 'limits' (DTI, LTV, credit score, retention "
            "period); a good system should ask for clarification rather than guess which one is meant."
        ),
    },
    {
        "id": "Q8", "category": "ambiguous",
        "question": "Is my loan high risk?",
        "expected_answer": (
            "Cannot be answered without specifics (DTI, LTV, credit score) for a particular loan; the "
            "documents define the criteria but the question provides no loan to evaluate them against."
        ),
    },
    {
        "id": "Q9", "category": "unanswerable",
        "question": "What is the current 30-year mortgage interest rate published by the Federal Reserve?",
        "expected_answer": "Not present in the lending-policy documents (they cover internal underwriting policy, not market rates).",
    },
    {
        "id": "Q10", "category": "unanswerable",
        "question": "What is the minimum down payment required for a mortgage in Canada?",
        "expected_answer": "Not present in the lending-policy documents (they are U.S.-focused; Canada is not covered).",
    },
]


def main() -> None:
    results = []
    for item in EVALUATION_QUESTIONS:
        rag_answer = answer_question(item["question"])
        results.append(
            {
                "id": item["id"],
                "category": item["category"],
                "question": item["question"],
                "expected_answer": item["expected_answer"],
                "generated_answer": rag_answer.answer,
                "is_answerable_by_system": rag_answer.is_answerable,
                "citations": rag_answer.citations,
                "retrieved_passages": rag_answer.retrieved_passages,
            }
        )

    paths = get_paths()
    reports_dir: Path = paths["reports_dir"]
    reports_dir.mkdir(parents=True, exist_ok=True)
    out_path = reports_dir / "rag_evaluation_raw.json"
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=2)
    print(f"Wrote {len(results)} evaluation result(s) to {out_path}")


if __name__ == "__main__":
    main()
