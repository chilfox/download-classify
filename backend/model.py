"""Lazy real-model boundary; ordinary tests replace this without model imports."""
import os

from backend.model_input import ENCODED_TOKEN_BUDGET, prepare_input

MODEL_ID = "fastino/gliner2-multi-v1"
REVISION = "ce747d79a8e362d3dee0b0b26d1201f7f1a8615a"


class LocalModel:
    def load(self):
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
        from gliner2 import GLiNER2

        self.model = GLiNER2.from_pretrained(MODEL_ID, revision=REVISION, local_files_only=True).to("cpu").eval()

    def schema(self, categories):
        if not categories:
            raise ValueError("No topic categories configured")
        return self.model.create_schema().classification(
            "document_topic", categories, multi_label=True, cls_threshold=0.0, class_act="sigmoid",
        )

    def validate_categories(self, categories):
        schema = self.schema(categories)
        batch = self.model.processor.collate_fn_inference([("", schema.build())], max_len=None)
        if int(batch.input_ids.shape[1]) > ENCODED_TOKEN_BUDGET:
            raise ValueError("Category schema alone exceeds the 512 encoded-token input budget")

    def classify(self, opening, categories):
        schema = self.schema(categories)
        prepared = prepare_input(self.model.processor, schema, opening)
        output = self.model.extract(prepared.text, schema, include_confidence=True, max_len=None)
        candidates = output["document_topic"]
        scores = {item["label"]: item["confidence"] for item in candidates}
        if len(scores) != len(candidates):
            raise ValueError("Model returned duplicate candidate labels")
        return scores, prepared.truncated, prepared.encoded_tokens
