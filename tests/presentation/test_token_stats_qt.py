"""
Tests cho TokenStatsPanelQt.
"""

import pytest
from unittest.mock import MagicMock
from domain.ports.registry import DomainRegistry
from domain.config.app_settings import AppSettings
from presentation.components.token_stats_qt import TokenStatsPanelQt


class DummySettingsService:
    def __init__(self) -> None:
        self._settings = AppSettings(model_id="gpt-5.1", use_gitignore=True)

    def load_settings(self) -> AppSettings:
        return self._settings

    def update_setting(self, key: str, value: str) -> None:
        setattr(self._settings, key, value)


@pytest.fixture(autouse=True)
def setup_settings_port():
    old_service = None
    old_provider = None
    try:
        old_service = DomainRegistry.settings_service()
    except RuntimeError:
        pass

    old_provider = DomainRegistry._settings_provider

    service = DummySettingsService()
    DomainRegistry.register_settings_service(service)
    DomainRegistry.register_settings_provider(lambda: service.load_settings())

    yield service

    if old_service is not None:
        DomainRegistry.register_settings_service(old_service)
    DomainRegistry._settings_provider = old_provider


def test_token_stats_panel_initial_state(qtbot):
    mock_tok = MagicMock()
    panel = TokenStatsPanelQt(mock_tok)
    qtbot.addWidget(panel)
    panel.show()

    # Initial values should be 0
    assert panel._file_count == 0
    assert panel._file_tokens == 0
    assert panel._instruction_tokens == 0
    assert panel._selected_model_id == "gpt-5.1"


def test_token_stats_panel_update_stats(qtbot):
    mock_tok = MagicMock()
    panel = TokenStatsPanelQt(mock_tok)
    qtbot.addWidget(panel)
    panel.show()

    # 1. Normal usage (e.g. 50k / 200k context length of GPT-5.1)
    panel.update_stats(file_count=5, file_tokens=40000, instruction_tokens=10000)
    assert panel._usage_label.text() == "50,000 / 200,000"
    assert panel._percentage_label.text() == "25.0%"
    assert panel._warning_banner.isHidden()

    # 2. Medium usage (say, 78% of context length)
    # We can temporarily mock self._selected_model.context_length to 100,000 for easier numbers
    panel._selected_model = MagicMock()
    panel._selected_model.context_length = 100000

    # 78k = 78% (Medium warning level)
    panel.update_stats(file_count=5, file_tokens=70000, instruction_tokens=8000)
    assert panel._usage_label.text() == "78,000 / 100,000"
    assert panel._percentage_label.text() == "78.0%"
    assert panel._warning_banner.isHidden()

    # 3. High usage (92% warning level)
    panel.update_stats(file_count=5, file_tokens=90000, instruction_tokens=2000)
    assert panel._usage_label.text() == "92,000 / 100,000"
    assert panel._percentage_label.text() == "92.0%"
    assert not panel._warning_banner.isHidden()
    assert "Approaching limit" in panel._warning_label.text()

    # 4. Critical usage (> 100%)
    panel.update_stats(file_count=5, file_tokens=105000, instruction_tokens=0)
    assert panel._usage_label.text() == "105,000 / 100,000"
    assert panel._percentage_label.text() == "105.0%"
    assert not panel._warning_banner.isHidden()
    assert "Exceeds limit" in panel._warning_label.text()


def test_token_stats_panel_model_changed(qtbot):
    mock_tok = MagicMock()
    panel = TokenStatsPanelQt(mock_tok)
    qtbot.addWidget(panel)
    panel.show()

    emitted = []
    panel.model_changed.connect(lambda m: emitted.append(m))

    # Find the index for gemini-3-pro
    target_idx = -1
    for idx in range(panel._model_combo.count()):
        if panel._model_combo.itemData(idx) == "gemini-3-pro":
            target_idx = idx
            break

    assert target_idx >= 0

    # Change index via combo box
    panel._model_combo.setCurrentIndex(target_idx)

    assert panel._selected_model_id == "gemini-3-pro"
    assert emitted == ["gemini-3-pro"]
    mock_tok.reset_encoder.assert_called_once()
    assert DomainRegistry.settings().model_id == "gemini-3-pro"


def test_token_stats_panel_set_loading(qtbot):
    mock_tok = MagicMock()
    panel = TokenStatsPanelQt(mock_tok)
    qtbot.addWidget(panel)
    panel.set_loading(True)
    assert panel._is_loading is True
    panel.set_loading(False)
    assert panel._is_loading is False


def test_token_stats_panel_invalid_saved_model(qtbot, setup_settings_port):
    # Set invalid model_id in settings
    setup_settings_port.update_setting("model_id", "invalid-model")

    mock_tok = MagicMock()
    panel = TokenStatsPanelQt(mock_tok)
    qtbot.addWidget(panel)
    # Should fall back to DEFAULT_MODEL_ID
    from domain.config.model_config import DEFAULT_MODEL_ID

    assert panel._selected_model_id == DEFAULT_MODEL_ID
