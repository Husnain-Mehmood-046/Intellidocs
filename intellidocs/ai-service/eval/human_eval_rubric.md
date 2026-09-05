# Human Evaluation Rubric for IntelliDocs Agent

## Overview
This rubric is used to manually score agent responses on three dimensions: **Relevance**, **Faithfulness**, and **Helpfulness**. Each dimension is scored 1–5.

Use this rubric when reviewing evaluation outputs to provide human judgment beyond automated metrics.

---

## Dimension 1: Relevance (Did it address the question?)

**Definition**: How well does the response address the user's actual question? Does it stay on topic and provide the information requested?

| Score | Description | Examples |
|-------|-------------|----------|
| **1 - Irrelevant** | Response is completely off-topic, answers a different question, or is nonsensical. | Q: "What are the findings?" → A: "The document was uploaded on Tuesday." |
| **2 - Partially Relevant** | Response touches on the topic but misses the core question or answers only a small part. | Q: "Summarize the methodology" → A: "The study used some methods and had participants." |
| **3 - Adequate** | Response addresses the main question but may lack depth, miss nuances, or include some extraneous info. | Q: "What are the conclusions?" → A: "The study found X and Y. Also mentions limitations." |
| **4 - Highly Relevant** | Response directly and comprehensively answers the question with appropriate detail level. | Q: "What are the conclusions?" → A: "The study concluded that X causes Y (p<0.05), with three main findings: 1) ... 2) ... 3) ... Limitations include..." |
| **5 - Perfectly Targeted** | Response answers exactly what was asked, anticipates follow-ups, and structures information optimally for the user's likely intent. | Q: "What are the conclusions?" → A: "Key conclusions: 1) X causes Y (p<0.05, n=500). 2) Effect is stronger in group A. 3) No effect in control. Practical implication: [specific recommendation]. Caveats: [specific limitations]." |

---

## Dimension 2: Faithfulness (Is it grounded in evidence?)

**Definition**: Is the response actually supported by the retrieved context / tool results? No hallucination, no invented facts, no claims beyond what the sources support.

| Score | Description | Examples |
|-------|-------------|----------|
| **1 - Hallucinated** | Major claims are invented, contradict sources, or cite non-existent information. | Source says "50% improvement" → Response says "90% improvement" or "doubled the results." |
| **2 - Mostly Ungrounded** | Some correct info but mixed with unsupported claims; citations don't match assertions. | Response makes 3 claims, only 1 supported by citations; other 2 are speculative. |
| **3 - Partially Grounded** | Core answer is supported but includes some overgeneralization or minor unsupported details. | "The study found significant results" (source: "p=0.04") but adds "across all demographics" (not in source). |
| **4 - Well Grounded** | All substantive claims trace to cited sources; appropriately hedges where evidence is thin. | "The study found X (p=0.04, Source 1). The authors note this may not generalize (Source 2)." |
| **5 - Rigorously Grounded** | Every claim explicitly linked to specific source; distinguishes between what sources say vs. what they imply; flags gaps honestly. | "Source 1 states X. Source 2 adds Y. Neither addresses Z, so we cannot conclude Z. Confidence: medium." |

---

## Dimension 3: Helpfulness (Would a real user find this useful?)

**Definition**: Beyond correctness, is the response actionable, clear, and valuable? Does it help the user accomplish their goal?

| Score | Description | Examples |
|-------|-------------|----------|
| **1 - Useless** | Response is confusing, misleading, or provides no actionable information. | "Maybe. It depends." (with no elaboration) or technical jargon without explanation. |
| **2 - Minimally Helpful** | Provides some info but requires significant effort from user to extract value. | Long unstructured wall of text; citations but no synthesis; answers "what" but not "so what." |
| **3 - Moderately Helpful** | Gives a decent answer that a motivated user can work with. | Clear answer with citations; missing practical next steps or context. |
| **4 - Very Helpful** | Well-structured, actionable, anticipates follow-up needs; good balance of depth and brevity. | Summary + key points + citations + "This means you should..." + "See also: [related topic]." |
| **5 - Exceptionally Helpful** | Transforms raw information into insight; tailored to likely user intent; enables immediate action. | Executive summary + decision-ready findings + confidence assessment + specific recommendations + caveats + suggested next queries. |

---

## Scoring Guidelines

### When to Score
- Score each evaluation response after running `run_eval.py`
- Score a representative sample (at least 10-15 responses) for statistical validity
- Score blind to the automated metrics if possible

### Recording Scores
Record scores in a CSV or JSON format alongside the eval report:

```json
{
  "eval_run_id": "eval_20260903_143022",
  "human_scores": [
    {
      "question_id": "rag_001",
      "relevance": 4,
      "faithfulness": 5,
      "helpfulness": 4,
      "notes": "Good answer but could be more concise"
    },
    ...
  ],
  "reviewer": "your_name",
  "date": "2026-09-03"
}
```

### Calibration Tips
1. **Score independently first**, then discuss with another reviewer to calibrate
2. **Use the examples** as anchors - compare each response to the level descriptions
3. **Don't overthink** - first impression is usually reliable for these dimensions
4. **Flag edge cases** with notes for later discussion

---

## Special Considerations by Response Type

### For Clarification Responses
- **Relevance**: Does the clarification question actually resolve the ambiguity?
- **Faithfulness**: N/A (no factual claims)
- **Helpfulness**: Is the question clear, specific, and easy for the user to answer?

### For Tool-Use Responses
- **Faithfulness**: Critical - verify the tool result was correctly interpreted
- **Relevance**: Did the tool choice make sense for the question?
- **Helpfulness**: Was the tool result synthesized well, or just dumped?

### For "I Don't Know" Responses
- **Relevance**: High if it honestly admits limitation
- **Faithfulness**: High (no false claims)
- **Helpfulness**: Depends on whether it suggests alternatives (search web, rephrase, upload doc)

---

## Aggregate Metrics

After scoring multiple responses, compute:

- **Mean Relevance**: Average across all scored responses
- **Mean Faithfulness**: Average across all scored responses  
- **Mean Helpfulness**: Average across all scored responses
- **Composite Score**: (Relevance + Faithfulness + Helpfulness) / 3
- **Pass Rate**: % of responses with all three dimensions ≥ 3

Target for Week 3 demo: **Composite ≥ 3.5, Pass Rate ≥ 70%**

---

## Integration with Automated Eval

The human scores complement automated metrics:

| Automated | Human |
|-----------|-------|
| Path accuracy (router correctness) | Relevance (answer quality) |
| Keyword match (answer_score) | Faithfulness (grounding) |
| Latency / Cost | Helpfulness (user value) |

**Recommendation**: Run automated eval first, then human-eval a stratified sample (some from each path, some high/low automated scores).