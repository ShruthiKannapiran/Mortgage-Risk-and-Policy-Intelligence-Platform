# RAG Evaluation Results

Evaluated against `data/policy_documents/` (7 documents, 23 chunks) using the extractive
pipeline in `src/rag/`. Raw retrieval/answer data: `reports/rag_evaluation_raw.json`.

| ID | Category | Correct? | Notes |
|---|---|---|---|
| Q1 | direct_factual | Yes | Exact match to expected answer (DTI 45%/50%). |
| Q2 | direct_factual | Yes | Exact match (FHA LTV 96.5%/90%). |
| Q3 | direct_factual | Yes | Exact match (25-month retention). |
| Q4 | direct_factual | Yes | Exact match (Tier 4, 660-699). |
| Q5 | cross_section | No | See below — misses the actual question. |
| Q6 | cross_section | Yes | Correct fact present, but not the lead passage. |
| Q7 | ambiguous | Yes (by luck) | Correctly refuses, but for the wrong reason. |
| Q8 | ambiguous | No | See below — false confidence. |
| Q9 | unanswerable | Yes | Correctly refuses. |
| Q10 | unanswerable | Yes | Correctly refuses. |

**Score: 8/10.**

## Detailed findings

### Q1-Q4 (direct factual) — all correct
Each question retrieved the exact policy section needed as the top result (similarity
0.72-0.82) and the composed answer matches the expected answer word-for-word, since the
source text itself contains the answer verbatim. This is the case the extractive
approach handles best: a single-section factual lookup.

### Q5 (cross-section) — incorrect: misses the actual question
**Question:** "If a Texas home-equity loan exceeds the state's LTV cap, is that
automatically considered high-risk?"
**Generated answer:** returned the High-Risk Criteria and LTV-policy high-risk sections
(both about the 95% LTV trigger), but **never mentioned the Texas 80% cap at all** — the
"State-Specific Lending Overlays" passage scored 0.5359, just under the 0.55 threshold,
so it was silently dropped from the answer.
**Why this matters:** the question requires connecting two separate facts (Texas caps
home-equity LTV at 80%; high-risk starts at 95%) to reach a conclusion ("no, these are
distinct rules"). The system can only paste back whatever clears the similarity
threshold — it has no mechanism to reason across passages or notice a relevant passage
was excluded by a hair. This is the core structural limitation of extractive RAG:
correct retrieval of *some* relevant content is not the same as answering the question
asked.

### Q6 (cross-section) — correct, but poorly ordered
The correct fact ("credit score below 660 + DTI above 40% requires manual underwriting")
**is** present in the answer, so I'm scoring this correct — but it's the *second*
passage, behind a DTI-high-risk passage (43% threshold) that doesn't actually match the
40% figure in the question. A user skimming only the first passage would get a subtly
wrong impression (43% vs. 40%). Ranking by similarity score doesn't guarantee the most
*directly responsive* passage comes first.

### Q7 (ambiguous) — correct outcome, wrong reason
"What's the limit?" scored only 0.24 similarity — far below threshold — so the system
correctly refuses rather than guessing which "limit" is meant. But it refuses with "I
don't have information about that," which is misleading: the information *does* exist
(multiple limits are defined), the question is just too vague to retrieve confidently. A
better response would detect the ambiguity explicitly and ask "which limit — DTI, LTV,
credit score, or retention period?" rather than implying the topic is uncovered. The
system gets a safe outcome for the wrong underlying reason.

### Q8 (ambiguous) — incorrect: false confidence
**Question:** "Is my loan high risk?"
**Generated answer:** returned the full High-Risk Triggers list as if it directly
answered the question. Similarity score (0.62) cleared the threshold because the
question is topically close to the high-risk-criteria document — but the question
provides no actual loan details (no DTI, LTV, or credit score) to evaluate against those
criteria. The system has no way to detect "this question is missing required inputs" —
it only measures topical similarity, not answerability given missing context. This is
the most important limitation surfaced by this evaluation: **a topically relevant match
is not the same as a valid answer**, and a user could easily misread this response as
"my loan meets none of these criteria" when nothing was actually evaluated.

### Q9-Q10 (unanswerable) — both correct
Both score well below the 0.55 threshold (0.43, 0.44) and correctly return the
not-found message rather than fabricating an answer about the Federal Reserve or
Canadian mortgage rules. This is the threshold mechanism working exactly as intended —
the primary defense against hallucination in this design.

## Summary

- **What works well:** single-fact, single-section lookups (Q1-Q4) and genuinely
  out-of-scope questions (Q9-Q10) — the two ends of the difficulty spectrum.
- **What doesn't:** anything requiring cross-passage reasoning (Q5) or recognizing that
  a question lacks the specifics needed to apply retrieved criteria (Q8). Both failures
  share a root cause — the system measures *topical similarity*, not *whether retrieved
  content actually resolves the question* — which is the fundamental ceiling of an
  extractive (non-generative) design.
- **Fix path:** swapping `compose_answer` for a hosted LLM call (see
  `src/rag/generation.py`'s docstring) that receives the same retrieved passages as
  context would let the model explicitly reason "these are two separate thresholds" (Q5)
  or "I need your DTI/LTV/credit score to answer this" (Q8) — retrieval quality is
  already adequate; synthesis is the gap.
