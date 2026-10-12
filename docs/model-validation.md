# Local model validation guide

## Purpose and commands

Validate the real local model independently of API health and ordinary tests. From the repository root:

```sh
uv sync --extra model-check --extra test --python 3.12
# First-time setup may download weights; subsequent acceptance uses cached weights.
uv run --extra model-check python scripts/model_smoke.py
uv run --extra model-check python scripts/model_acceptance.py \
  --output /tmp/model-acceptance-results.json
```

The smoke checks loading and basic inference, not classification quality. The non-moving acceptance script runs the labeled English/Traditional Chinese TXT/Markdown fixtures in `fixtures/model-acceptance/`, records all candidate scores, token counts, accuracy, threshold eligibility and latency, and checks bounded excerpts with large inputs. Ordinary tests replace only the model boundary and do not establish model quality.

The checkpoint is `fastino/gliner2-multi-v1`, revision `ce747d79a8e362d3dee0b0b26d1201f7f1a8615a`. Acceptance runs serially on CPU, using cached weights with HF offline mode and telemetry disabled. No document contents or filenames are sent to cloud services. Missing weights or loading/inference failures must be reported as failures, not fabricated suggestions.

## Score contract and movement policy

Use GLiNER2 multi-label classification with `cls_threshold=0.0`, `class_act="sigmoid"`, no `top_k`, and `include_confidence=True`. Validate one finite score in [0, 1] for every configured category. These independent sigmoid scores do not have to sum to one and are not calibrated probabilities of correctness. Winning-only output is insufficient to compute ambiguity.

`backend/classification.py` shares ranking and fixed decision thresholds between runtime and acceptance: top score >=0.65 and top-two gap >=0.10. A single category still requires the minimum score; no gap is required without a runner-up. NeedsReview is not a model category. Clear results choose one topic; successfully classified uncertain results choose NeedsReview in automatic mode. Processing/model errors remain untouched. Suggestions-only mode never moves files.

## Bounded input policy

`backend/model_input.py` reads a bounded opening of at most 64 KiB plus one detection byte and fits a Unicode-safe opening excerpt to **512 encoded tokens including the captured schema, prefix and special tokens**. Use the prepared text with that same schema and `max_len=None`; do not assume a 512-word cap or tokenizer sentinel bounds actual encoder tokens.

The user approved automatic topic/NeedsReview movement based on excerpts at the same thresholds. Original contents must not change; results disclose truncation. Long-document classification quality remains unvalidated. Opening UTF-8 errors, unusable text and schemas that alone exceed the budget fail explicitly. Unread file tails are not validated. The 512-token budget is a conservative configured context budget, not a claim of a hard architectural ceiling.

## Evidence and limitations

Saved MVP observations and raw data are in [the model acceptance report](../test-results/download-classify-mvp/model-acceptance.md) and [its JSON](../test-results/download-classify-mvp/model-acceptance.json). These are historical evidence recorded with a 0.80 minimum score and 0.20 minimum gap, not automatically refreshed results. The current 0.65 minimum score and 0.10 minimum gap were requested by the user; those historical coverage results do not validate the new threshold. See [the complete workflow guide](demo-validation.md) for API/monitor/movement validation.

Report prediction accuracy separately from automatic topic-movement eligibility/coverage. Use independently labeled expected topics; do not count NeedsReview routing as a correct topic prediction. The small synthetic fixture set is not representative production evidence. Do not lower thresholds to hide poor quality. Dependency warnings and failures must be disclosed.
