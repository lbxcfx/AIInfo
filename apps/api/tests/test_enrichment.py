from app.services.enrichment import final_score_from_dimensions, normalize_category


class SourceLike:
    tier = "T1"
    reliability_score = 90


def test_normalize_category_falls_back() -> None:
    assert normalize_category("unknown", "行业动态") == "行业动态"


def test_final_score_from_dimensions_increases_with_scores() -> None:
    low = final_score_from_dimensions(
        SourceLike(),
        0.7,
        "行业动态",
        {
            "novelty": 30,
            "impact": 30,
            "actionability": 30,
            "source_quality": 70,
            "freshness": 30,
        },
    )
    high = final_score_from_dimensions(
        SourceLike(),
        0.9,
        "模型发布/更新",
        {
            "novelty": 90,
            "impact": 90,
            "actionability": 80,
            "source_quality": 90,
            "freshness": 80,
        },
    )
    assert high > low
