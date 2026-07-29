"""Exact BERT masked-language-model configurations approved for NEU LAB."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from transformers import BertConfig, BertForMaskedLM

VOCAB_SIZE = 8_000
MAX_SEQUENCE_LENGTH = 128
PAD_TOKEN_ID = 0
UNK_TOKEN_ID = 1
CLS_TOKEN_ID = 2
SEP_TOKEN_ID = 3
MASK_TOKEN_ID = 4
SPECIAL_TOKEN_IDS = frozenset(
    {PAD_TOKEN_ID, UNK_TOKEN_ID, CLS_TOKEN_ID, SEP_TOKEN_ID, MASK_TOKEN_ID}
)
CONDITIONS = ("EnglishMono", "SpanishMono", "MonoCont", "CsCont")

TRANSFORMERS_VERSION = "5.6.2"
TORCH_VERSION = "2.11.0"
TOKENIZERS_VERSION = "0.22.2"
NUMPY_VERSION = "1.26.4"


class ModelContractError(RuntimeError):
    """An approved model invariant was violated."""


class ModelSize(str, Enum):
    """The only model sizes authorized by this gate."""

    TINY = "neu_tiny"
    SMALL = "neu_small"


_APPROVED_DIMENSIONS = {
    ModelSize.TINY: (2, 128, 2, 512, 1_462_080),
    ModelSize.SMALL: (4, 256, 4, 1_024, 5_314_880),
}


@dataclass(frozen=True)
class ModelSpecification:
    """Typed, canonical representation of an approved model configuration."""

    name: ModelSize
    vocabulary_size: int
    maximum_sequence_length: int
    num_hidden_layers: int
    hidden_size: int
    num_attention_heads: int
    intermediate_size: int
    hidden_activation: str
    hidden_dropout: float
    attention_dropout: float
    initializer_range: float
    layer_norm_epsilon: float
    type_vocabulary_size: int
    position_embedding_type: str
    use_cache: bool
    tie_word_embeddings: bool
    pad_token_id: int
    unk_token_id: int
    cls_token_id: int
    sep_token_id: int
    mask_token_id: int
    objective: str
    next_sentence_prediction: bool
    pretrained_weights: bool
    expected_trainable_parameters: int

    def __post_init__(self) -> None:
        try:
            approved_dimensions = _APPROVED_DIMENSIONS[self.name]
        except (KeyError, TypeError) as exc:
            raise ModelContractError("unknown model size") from exc
        actual_common = (
            self.vocabulary_size,
            self.maximum_sequence_length,
            self.hidden_activation,
            self.hidden_dropout,
            self.attention_dropout,
            self.initializer_range,
            self.layer_norm_epsilon,
            self.type_vocabulary_size,
            self.position_embedding_type,
            self.use_cache,
            self.tie_word_embeddings,
            self.pad_token_id,
            self.unk_token_id,
            self.cls_token_id,
            self.sep_token_id,
            self.mask_token_id,
            self.objective,
            self.next_sentence_prediction,
            self.pretrained_weights,
        )
        expected_common = (
            8_000,
            128,
            "gelu",
            0.1,
            0.1,
            0.02,
            1e-12,
            1,
            "absolute",
            False,
            True,
            0,
            1,
            2,
            3,
            4,
            "masked_language_modeling",
            False,
            False,
        )
        actual_dimensions = (
            self.num_hidden_layers,
            self.hidden_size,
            self.num_attention_heads,
            self.intermediate_size,
            self.expected_trainable_parameters,
        )
        if actual_common != expected_common or actual_dimensions != approved_dimensions:
            raise ModelContractError("model specification differs from the approved contract")

    def canonical_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["name"] = self.name.value
        return result

    def configuration_sha256(self) -> str:
        return hashlib.sha256(_canonical_json_bytes(self.canonical_dict())).hexdigest()

    def to_bert_config(self) -> BertConfig:
        """Create the exact encoder configuration; no pretrained loader is used."""
        config = BertConfig(
            vocab_size=self.vocabulary_size,
            hidden_size=self.hidden_size,
            num_hidden_layers=self.num_hidden_layers,
            num_attention_heads=self.num_attention_heads,
            intermediate_size=self.intermediate_size,
            hidden_act=self.hidden_activation,
            hidden_dropout_prob=self.hidden_dropout,
            attention_probs_dropout_prob=self.attention_dropout,
            initializer_range=self.initializer_range,
            layer_norm_eps=self.layer_norm_epsilon,
            max_position_embeddings=self.maximum_sequence_length,
            type_vocab_size=self.type_vocabulary_size,
            position_embedding_type=self.position_embedding_type,
            use_cache=self.use_cache,
            pad_token_id=self.pad_token_id,
            tie_word_embeddings=self.tie_word_embeddings,
            architectures=["BertForMaskedLM"],
            is_decoder=False,
            add_cross_attention=False,
        )
        validate_bert_config(config, self)
        return config


def _spec(
    name: ModelSize,
    *,
    layers: int,
    hidden: int,
    heads: int,
    intermediate: int,
    parameters: int,
) -> ModelSpecification:
    return ModelSpecification(
        name=name,
        vocabulary_size=VOCAB_SIZE,
        maximum_sequence_length=MAX_SEQUENCE_LENGTH,
        num_hidden_layers=layers,
        hidden_size=hidden,
        num_attention_heads=heads,
        intermediate_size=intermediate,
        hidden_activation="gelu",
        hidden_dropout=0.1,
        attention_dropout=0.1,
        initializer_range=0.02,
        layer_norm_epsilon=1e-12,
        type_vocabulary_size=1,
        position_embedding_type="absolute",
        use_cache=False,
        tie_word_embeddings=True,
        pad_token_id=PAD_TOKEN_ID,
        unk_token_id=UNK_TOKEN_ID,
        cls_token_id=CLS_TOKEN_ID,
        sep_token_id=SEP_TOKEN_ID,
        mask_token_id=MASK_TOKEN_ID,
        objective="masked_language_modeling",
        next_sentence_prediction=False,
        pretrained_weights=False,
        expected_trainable_parameters=parameters,
    )


_APPROVED_FIELDS = {
    ModelSize.TINY: _spec(
        ModelSize.TINY,
        layers=2,
        hidden=128,
        heads=2,
        intermediate=512,
        parameters=1_462_080,
    ),
    ModelSize.SMALL: _spec(
        ModelSize.SMALL,
        layers=4,
        hidden=256,
        heads=4,
        intermediate=1_024,
        parameters=5_314_880,
    ),
}

NEU_TINY = ModelSpecification(**asdict(_APPROVED_FIELDS[ModelSize.TINY]))
NEU_SMALL = ModelSpecification(**asdict(_APPROVED_FIELDS[ModelSize.SMALL]))


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def approved_model_specification(size: ModelSize | str) -> ModelSpecification:
    try:
        model_size = ModelSize(size)
    except ValueError as exc:
        raise ModelContractError("unknown model size") from exc
    approved = _APPROVED_FIELDS[model_size]
    return ModelSpecification(**asdict(approved))


def validate_bert_config(config: BertConfig, specification: ModelSpecification) -> None:
    """Fail closed if a Transformers configuration drifts from the typed contract."""
    actual = {
        "vocab_size": config.vocab_size,
        "max_position_embeddings": config.max_position_embeddings,
        "num_hidden_layers": config.num_hidden_layers,
        "hidden_size": config.hidden_size,
        "num_attention_heads": config.num_attention_heads,
        "intermediate_size": config.intermediate_size,
        "hidden_act": config.hidden_act,
        "hidden_dropout_prob": config.hidden_dropout_prob,
        "attention_probs_dropout_prob": config.attention_probs_dropout_prob,
        "initializer_range": config.initializer_range,
        "layer_norm_eps": config.layer_norm_eps,
        "type_vocab_size": config.type_vocab_size,
        "position_embedding_type": config.position_embedding_type,
        "use_cache": config.use_cache,
        "tie_word_embeddings": config.tie_word_embeddings,
        "pad_token_id": config.pad_token_id,
        "is_decoder": config.is_decoder,
        "add_cross_attention": config.add_cross_attention,
        "architectures": config.architectures,
    }
    expected = {
        "vocab_size": specification.vocabulary_size,
        "max_position_embeddings": specification.maximum_sequence_length,
        "num_hidden_layers": specification.num_hidden_layers,
        "hidden_size": specification.hidden_size,
        "num_attention_heads": specification.num_attention_heads,
        "intermediate_size": specification.intermediate_size,
        "hidden_act": specification.hidden_activation,
        "hidden_dropout_prob": specification.hidden_dropout,
        "attention_probs_dropout_prob": specification.attention_dropout,
        "initializer_range": specification.initializer_range,
        "layer_norm_eps": specification.layer_norm_epsilon,
        "type_vocab_size": specification.type_vocabulary_size,
        "position_embedding_type": specification.position_embedding_type,
        "use_cache": False,
        "tie_word_embeddings": True,
        "pad_token_id": PAD_TOKEN_ID,
        "is_decoder": False,
        "add_cross_attention": False,
        "architectures": ["BertForMaskedLM"],
    }
    if actual != expected:
        raise ModelContractError("Transformers configuration differs from approved fields")


def validate_model(model: BertForMaskedLM, specification: ModelSpecification) -> int:
    """Audit the objective, trainable count, and tied input/output embeddings."""
    if not isinstance(model, BertForMaskedLM):
        raise ModelContractError("model is not a BERT masked-language model")
    validate_bert_config(model.config, specification)
    parameter_count = sum(
        parameter.numel() for parameter in model.parameters() if parameter.requires_grad
    )
    if parameter_count != specification.expected_trainable_parameters:
        raise ModelContractError("trainable parameter count differs from approved design")
    input_weight = model.get_input_embeddings().weight
    output_weight = model.get_output_embeddings().weight
    if input_weight is not output_weight or input_weight.data_ptr() != output_weight.data_ptr():
        raise ModelContractError("input and output word embeddings are not tied")
    return parameter_count
