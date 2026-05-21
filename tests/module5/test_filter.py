def test_build_filter_none_for_empty():
    from modules.module5_retrieve.tag import build_filter
    assert build_filter(None) is None
    assert build_filter({}) is None


def test_build_filter_mesh_terms():
    from modules.module5_retrieve.tag import build_filter
    from qdrant_client.models import MatchAny
    f = build_filter({'mesh_terms': ['Metformin', 'Diabetes']})
    assert f is not None
    assert len(f.must) == 1
    assert f.must[0].key == 'mesh_terms'
    assert isinstance(f.must[0].match, MatchAny)


def test_build_filter_year_range():
    from modules.module5_retrieve.tag import build_filter
    from qdrant_client.models import Range
    f = build_filter({'year_from': 2020, 'year_to': 2023})
    assert f is not None
    cond = next(c for c in f.must if c.key == 'pub_year')
    assert isinstance(cond.range, Range)
    assert cond.range.gte == 2020
    assert cond.range.lte == 2023


def test_build_filter_multiple_conditions():
    from modules.module5_retrieve.tag import build_filter
    f = build_filter({
        'mesh_terms': ['Metformin'],
        'year_from': 2020,
        'element_type': 'section',
    })
    assert len(f.must) == 3


def test_build_filter_source_db():
    from modules.module5_retrieve.tag import build_filter
    from qdrant_client.models import MatchValue
    f = build_filter({'source_db': 'pubmed'})
    assert f.must[0].match == MatchValue(value='pubmed')
