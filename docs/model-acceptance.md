# Local model acceptance

## Decision and status

The real multilingual model meets the small demo prediction target: **11/12 correct** (91.7%). At fixed minimum sigmoid score **0.80** and top-two gap **0.20**, **11/12** documents qualify for automatic movement (91.7% coverage), all 11 correctly predicted. The remaining clinical-trial manuscript incorrectly predicts Medical report instead of Academic research, but fails both thresholds and would go to NeedsReview. English accuracy is 5/6; Traditional Chinese is 6/6.

Recommendation: automatic mode is justified for this disposable demo's **complete, bounded inputs only**, subject to the user approving the input policy. This is not production-quality evidence, calibrated confidence, or a guarantee for arbitrary user categories. The fixtures are hand-authored synthetic examples, not a held-out representative corpus. Thresholds were proposed as conservative cutoffs and retained after observing these results: the lowest qualifying score is 0.865; the lowest qualifying gap is 0.415. The one wrong prediction has score 0.422 and gap 0.147. Do not tune them down to increase coverage.

**Ticket 01 remains claimed pending the user decision. No movement implementation is present in this ticket.** Until policy approval, run validation only or disclose suggestions-only behavior. If loading fails, report model unavailable and leave files untouched; do not fabricate suggestions.

## Repeatable local run

```sh
uv sync --extra model-check --extra test --python 3.12
uv run --extra model-check python scripts/model_acceptance.py --output /tmp/model-acceptance-results.json
```

The script pins `fastino/gliner2-multi-v1` revision `ce747d79a8e362d3dee0b0b26d1201f7f1a8615a`, loads once on CPU, processes the 12 labeled UTF-8 TXT/Markdown fixtures serially, and writes every candidate score, token count, correctness, decision and latency. It never moves files. Model downloads must be completed separately if the checkpoint is not cached (the README smoke command permits the initial download). Acceptance sets `HF_HUB_OFFLINE=1` and disables HF telemetry before model imports, reusing the existing cache. No fixture content or filenames are sent to a cloud service.

The committed observed run is [model-acceptance-results.json](model-acceptance-results.json). Run provenance: current Apple Silicon MacBook, macOS 26.5.2, Python 3.12.11, gliner2 2.1.0, torch 2.14.1, transformers 5.19.0. Cache-backed loading took **3.31 seconds**, median per-document inference **0.078 seconds**, maximum **0.089 seconds**. Counts include schema/prefix and span from 241 to 280 encoded tokens. These are serial CPU measurements, not concurrent API responsiveness evidence. Ordinary pytest and `/health` neither initialize nor validate this model.

The dependency emits an extractor/model-type compatibility log and a `torch.jit.script` FutureWarning. Loading and all inferences completed nonetheless; these warnings are disclosed rather than suppressed. Ordinary tests run with warnings as errors without importing the model. Initial smoke also completed: load 3.69 seconds, Chinese/English inference 0.07/0.05 seconds. Its Chinese medical text was forced into Invoice because its three-label schema lacked Medical report; that two-example smoke is not quality acceptance.

## Candidate scoring contract for integration

Use the tested public API:

```python
schema = model.create_schema().classification(
    "document_topic", {name: description for name, description in categories},
    multi_label=True, cls_threshold=0.0, class_act="sigmoid",
)
output = model.extract(text, schema, include_confidence=True, max_len=None)
# output["document_topic"] is [{"label": name, "confidence": score}, ...]
```

Set no `top_k`. Validate that exactly every configured category returns a finite score between zero and one. Sort descending (stable name tie-break), compute `top_score - second_score`, and choose at most one final destination. Keep NeedsReview out of the model schema. For one topic, require score >= 0.80 but omit the nonexistent gap; sigmoid avoids the single-label softmax's forced score of one. No configured topics is not a classification success.

Verified in installed gliner2 2.1.0 `inference/runtime.py`, `_compute_classification_probabilities` and `_decode_classification_probabilities`: the classification head yields one logit per label; `class_act="sigmoid"` applies independent sigmoid at temperature 1. Threshold zero retains all candidates, allowing a genuine runner-up gap. Scores need not sum to one and are **not calibrated probabilities of correctness**. The default exclusive/single-label API instead applies softmax and returns only the winning label; do not use its winning-only output as the gap source. Changing activation, temperature or category prompt invalidates this numerical validation.

## Actual input-limit evidence and requested user policy

The checkpoint uses `microsoft/mdeberta-v3-base`. Its tokenizer advertises the enormous sentinel `1000000000000000019884624838656`, not a meaningful document limit. The encoder config has `max_position_embeddings=512`, relative attention, and `position_biased_input=false`. **512 is a conservative configured context budget, not a hard architectural ceiling**: a synthetic 868-token input successfully inferred in 0.271 seconds. This does not validate long-document quality or make unbounded input safe.

The processor does not implicitly truncate when `max_len=None`. Its `max_len` counts word-split tokens, not the final encoder subwords. With our four-category descriptions, 21,000 English characters yield 7,168 encoded tokens and a word cap of 512 still yields 1,062; 7,000 Traditional Chinese characters yield 7,168 tokens and the same word cap yields 1,958. Thus `max_len=512`, a character count, or tokenizer sentinel alone is not a reliable 512-subword bound. Category descriptions, classification prefix and special tokens also consume context. These preprocessing-only probes never encode the huge inputs.

**Recommended policy for user confirmation:** read at most 64 KiB plus one byte to detect oversize; require usable UTF-8 text; compute the full, unsampled processor input for the actual captured category schema; allow inference/movement only if the complete prompt and document fit 512 encoded tokens. Over 64 KiB or over that token budget: leave the original untouched and show an explicit overlong/unsupported-input result with the observed limit. Do not route it to NeedsReview, truncate it, or enable movement from an excerpt. If the schema alone exceeds the budget, report a configuration/input error without moving any document. The 64 KiB read bound is a resource guard, not a claim that every file within it fits the model.

Please approve that leave-untouched policy, or explicitly choose a disclosed excerpt/suggestions policy. No truncated-input movement is authorized. This script safely rejects over-budget acceptance fixtures before inference; the above-context synthetic probe is isolated non-moving research only. Application extraction and API/filesystem safety tests belong to the following processing ticket at the already approved seam.
