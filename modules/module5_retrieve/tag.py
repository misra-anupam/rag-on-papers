from qdrant_client.models import FieldCondition, Filter, MatchAny, MatchValue, Range


def build_filter(filters: dict | None) -> Filter | None:
    if not filters:
        return None
    conds = []
    if 'mesh_terms' in filters:
        conds.append(FieldCondition(
            key='mesh_terms', match=MatchAny(any=filters['mesh_terms'])
        ))
    if 'year_from' in filters:
        conds.append(FieldCondition(
            key='pub_year',
            range=Range(gte=filters['year_from'], lte=filters.get('year_to', 2100)),
        ))
    if 'journal' in filters:
        conds.append(FieldCondition(
            key='journal', match=MatchValue(value=filters['journal'])
        ))
    if 'element_type' in filters:
        conds.append(FieldCondition(
            key='element_type', match=MatchValue(value=filters['element_type'])
        ))
    if 'source_db' in filters:
        conds.append(FieldCondition(
            key='source_db', match=MatchValue(value=filters['source_db'])
        ))
    return Filter(must=conds) if conds else None
