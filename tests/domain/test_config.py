from domain.config.app_settings import AppSettings
from domain.config.model_config import get_model_by_id
from domain.config.output_format import OutputStyle
from domain.config.prompt_profiles import get_profile, list_profiles

def test_configs_integrity():
    settings = AppSettings()
    assert settings.use_gitignore is True
    assert get_model_by_id("gpt-5.1") is not None
    assert OutputStyle.XML.value == "xml"
    
    assert "review" in list_profiles()
    review_profile = get_profile("review")
    assert review_profile is not None
    assert review_profile.name == "review"

