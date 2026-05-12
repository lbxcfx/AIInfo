from app.core.text import ai_relevance_score, canonicalize_url, classify_category


def test_canonicalize_url_removes_tracking() -> None:
    url = canonicalize_url("https://Example.com/post/?utm_source=x&ref=y&a=1#section")
    assert url == "https://example.com/post?a=1"


def test_ai_relevance_scores_ai_content_higher() -> None:
    ai_score = ai_relevance_score("OpenAI releases model", "new LLM agent API")
    other_score = ai_relevance_score("Quarterly earnings", "retail store update")
    assert ai_score > other_score


def test_classify_model_release() -> None:
    assert classify_category("OpenAI announces new model", "") == "模型发布/更新"

