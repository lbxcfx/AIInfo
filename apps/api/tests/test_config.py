from app.core.config import get_settings


def test_settings_loads() -> None:
    settings = get_settings()
    assert settings.app_name == "ai-intel-radar"
    assert settings.llm_provider == "bigmodel"
    assert settings.embedding_model == "embedding-3"

