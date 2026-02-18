import pytest

from src.core.domain.persona_config import ImageUnderstandingConfig


def test_image_understanding_accepts_hybrid_mode():
    cfg = ImageUnderstandingConfig.from_dict({"retrieval_ab_mode": "hybrid"})
    assert cfg.retrieval_ab_mode == "hybrid"


def test_image_understanding_uses_2000_as_default_max_tokens():
    cfg = ImageUnderstandingConfig.from_dict({})
    assert cfg.max_tokens == 2000


@pytest.mark.parametrize("mode", ["ab_split", "unknown"])
def test_image_understanding_rejects_unsupported_mode(mode):
    with pytest.raises(ValueError):
        ImageUnderstandingConfig.from_dict({"retrieval_ab_mode": mode})
