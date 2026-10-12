# Local model acceptance

## Decision and status

The real multilingual model meets the small demo prediction target: **11/12 correct** (91.7%). At fixed minimum sigmoid score **0.80** and top-two gap **0.20**, **11/12** documents qualify for automatic movement (91.7% coverage), all 11 correctly predicted. The remaining clinical-trial manuscript incorrectly predicts Medical report instead of Academic research, but fails both thresholds and would go to NeedsReview. English accuracy is 5/6; Traditional Chinese is 6/6.

Decision: automatic mode is justified for this disposable demo. The user explicitly approved **opening-excerpt-based automatic movement, including NeedsReview**, using the same thresholds. The complete schema, prefix, special tokens and selected opening excerpt must fit 512 encoded tokens. The 11/12 result validates only the short fixtures, not long-document classification quality. This is not production-quality evidence, calibrated confidence, or a guarantee for arbitrary user categories. The fixtures are hand-authored synthetic examples, not a held-out representative corpus. Thresholds were proposed as conservative cutoffs and retained after observing these results: the lowest qualifying score is 0.865; the lowest qualifying gap is 0.415. The one wrong prediction has score 0.422 and gap 0.147. Do not tune them down to increase coverage.

**Ticket 01 is resolved. Its original validation was non-moving.** The completed backend now has independent real-model API/monitor/movement evidence: see [complete demonstration acceptance](demo-acceptance.md) and [raw results](demo-acceptance-results.json). The reusable input adapter and acceptance tool prepare approved excerpts without modifying source contents; the processing ticket implements movement and visible truncation disclosures. If loading fails, report model unavailable and leave files untouched; do not fabricate suggestions.

## Repeatable local run

```sh
uv sync --extra model-check --extra test --python 3.12
uv run --extra model-check python scripts/model_acceptance.py --output /tmp/model-acceptance-results.json
```

The script pins `fastino/gliner2-multi-v1` revision `ce747d79a8e362d3dee0b0b26d1201f7f1a8615a`, loads once on CPU, processes the 12 labeled UTF-8 TXT/Markdown fixtures serially, and writes every candidate score, token count, correctness, decision and latency. It never moves files. Model downloads must be completed separately if the checkpoint is not cached (the README smoke command permits the initial download). Acceptance sets `HF_HUB_OFFLINE=1` and disables HF telemetry before model imports, reusing the existing cache. No fixture content or filenames are sent to a cloud service.

The committed observed run is [model-acceptance-results.json](model-acceptance-results.json). Run provenance: current Apple Silicon MacBook, macOS 26.5.2, Python 3.12.11, gliner2 2.1.0, torch 2.14.1, transformers 5.19.0. Cache-backed loading took **3.17 seconds**, median per-document inference **0.077 seconds**, maximum **0.088 seconds**. Counts include schema/prefix and span from 241 to 280 encoded tokens. These are serial CPU measurements, not concurrent API responsiveness evidence. Ordinary pytest and `/health` neither initialize nor validate this model.

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

## Actual input-limit evidence and approved user policy

The checkpoint uses `microsoft/mdeberta-v3-base`. Its tokenizer advertises the enormous sentinel `1000000000000000019884624838656`, not a meaningful document limit. The encoder config has `max_position_embeddings=512`, relative attention, and `position_biased_input=false`. **512 is a conservative configured context budget, not a hard architectural ceiling**: a synthetic 868-token input successfully inferred in 0.268 seconds. This does not validate long-document quality or make unbounded input safe.

The processor does not implicitly truncate when `max_len=None`. Its `max_len` counts word-split tokens, not the final encoder subwords. With our four-category descriptions, 21,000 English characters yield 7,168 encoded tokens and a word cap of 512 still yields 1,062; 7,000 Traditional Chinese characters yield 7,168 tokens and the same word cap yields 1,958. Thus `max_len=512`, a character count, or tokenizer sentinel alone is not a reliable 512-subword bound. Category descriptions, classification prefix and special tokens also consume context. These preprocessing-only probes never encode the huge inputs.

**Explicitly approved user policy:** read at most 64 KiB plus one byte to detect oversize, then fit a Unicode opening prefix so the complete captured category schema, classification prefix, special tokens and excerpt together use at most 512 encoded tokens. A larger file is classified from the bounded opening, not rejected solely for size. Automatic topic movement and NeedsReview based on that excerpt are authorized at the same thresholds. Never modify source contents. Disclose `truncated`/excerpt-only in the result and dashboard; long-document quality remains unvalidated. Strict UTF-8 decoding validates the opening only, not unread tails; omit an incomplete codepoint at the read boundary rather than splitting Unicode or introducing replacement characters. Invalid UTF-8 within the opening, unusable text, or a schema that alone exceeds the budget fail explicitly and leave the file untouched.

`backend/model_input.py` exposes `read_opening(path)` and `prepare_input(processor, schema, opening)`. Use its returned text and encoded count with the same captured schema and `max_len=None`. Prefix search checks actual processor counts, not estimated word counts. It need not select the longest possible prefix because subword counts can be non-monotonic, but the final prefix is explicitly verified within budget. It imports no model dependencies and does no inference or movement. The processing caller still owns file-stability, symlink, extension and movement safety at the approved public API/temporary-filesystem test seam.

The repeatable acceptance run additionally creates disposable 210,000-byte English and Chinese inputs, bounds opening reads to 65,536 bytes, confirms prefix identity and unchanged source bytes, checks actual encoder input <=512, and runs real CPU inference on each excerpt. Both excerpts use 511 encoded tokens: 1,029 English characters and 343 Chinese characters; the Chinese read boundary splits a three-byte codepoint, which is safely omitted. These resource/input-safety probes are not additional labeled quality examples and do not contribute to the 11/12 accuracy or coverage. An oversized category-only schema is explicitly rejected before inference. The earlier above-context probe remains isolated non-moving research.
