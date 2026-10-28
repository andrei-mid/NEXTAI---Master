from verifirm.core.config import get_settings
from verifirm.schema.signals import Component
from verifirm.scoring.engine import load_scoring_config


def test_weights_yaml_is_valid_and_complete() -> None:
    config = load_scoring_config(get_settings().scoring_config_path)
    assert sum(config.weights.values()) == 100
    assert Component.MEDIA in config.never_stop_components
    assert set(config.bands.green_requires_components) == {Component.IDENTITY, Component.SANCTIONS}
