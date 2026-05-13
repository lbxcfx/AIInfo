from app.services.crawler import apply_source_specific_score, extract_repo_slugs


def test_low_github_metric_repo_is_capped() -> None:
    score = apply_source_specific_score(
        78.9,
        {"stars": 60, "forks": 15},
        "github_trending",
    )
    assert score <= 65


def test_high_github_metric_repo_can_rank_high() -> None:
    score = apply_source_specific_score(
        78.9,
        {"stars": 4000, "forks": 400, "stars_today": 120},
        "github_trending_page",
    )
    assert score > 85


def test_huggingface_trending_metrics_boost_score() -> None:
    score = apply_source_specific_score(
        72.0,
        {"downloads": 120000, "likes": 1500, "trending_rank": 3},
        "huggingface_trending",
    )
    assert score > 85


def test_extract_repo_slugs_from_github_links() -> None:
    html = '<a href="/sponsors/explore">bad</a><a href="/owner/repo">repo</a>'
    assert extract_repo_slugs(html, 10) == ["owner/repo"]
