"""Parse PubMed Central native XML (JATS format) into the shared structured.json schema."""
from lxml import etree


def parse_pmc_xml(raw_bytes: bytes) -> dict:
    root = etree.fromstring(raw_bytes)
    meta = root.find('.//article-meta')
    return {
        'doi':        _extract_doi(meta),
        'title':      _text(meta, './/article-title'),
        'abstract':   _extract_abstract(meta),
        'authors':    _extract_authors(meta),
        'journal':    _text(root, './/journal-title'),
        'pub_date':   _extract_pub_date(meta),
        'mesh_terms': _extract_mesh(root),
        'keywords':   [kw.text or '' for kw in root.findall('.//kwd') if kw.text],
        'sections':   _extract_sections(root),
        'figures':    _extract_figures(root),
        'tables':     _extract_tables(root),
    }


def _text(elem, xpath: str) -> str:
    if elem is None:
        return ''
    node = elem.find(xpath)
    if node is None:
        return ''
    return ''.join(node.itertext()).strip()


def _extract_doi(meta) -> str:
    if meta is None:
        return ''
    for aid in meta.findall('article-id'):
        if aid.get('pub-id-type') == 'doi' and aid.text:
            return aid.text.strip()
    return ''


def _extract_abstract(meta) -> str:
    if meta is None:
        return ''
    parts = []
    for abstract in meta.findall('abstract'):
        parts.append(''.join(abstract.itertext()).strip())
    return ' '.join(parts)


def _extract_authors(meta) -> list[dict]:
    authors = []
    if meta is None:
        return authors
    for contrib in meta.findall('.//contrib[@contrib-type="author"]'):
        surname  = _text(contrib, 'name/surname')
        forename = _text(contrib, 'name/given-names')
        name = f'{forename} {surname}'.strip()
        affil_id = ''
        xref = contrib.find('xref[@ref-type="aff"]')
        if xref is not None:
            affil_id = xref.get('rid', '')
        if name:
            authors.append({'name': name, 'affiliation': affil_id})
    return authors


def _extract_pub_date(meta) -> str:
    if meta is None:
        return ''
    for pub_date in meta.findall('pub-date'):
        if pub_date.get('pub-type') in ('epub', 'ppub', 'collection', None):
            year  = _text(pub_date, 'year')
            month = _text(pub_date, 'month').zfill(2) if _text(pub_date, 'month') else '01'
            day   = _text(pub_date, 'day').zfill(2) if _text(pub_date, 'day') else '01'
            if year:
                return f'{year}-{month}-{day}'
    return ''


def _extract_mesh(root) -> list[str]:
    terms = []
    for mh in root.findall('.//MeshHeading/DescriptorName'):
        if mh.text:
            terms.append(mh.text.strip())
    return terms


def _extract_sections(root) -> list[dict]:
    sections = []
    body = root.find('.//body')
    if body is None:
        return sections
    for sec in body.findall('.//sec'):
        heading = _text(sec, 'title')
        paras   = [' '.join(p.itertext()).strip() for p in sec.findall('p')]
        fig_refs = [xref.get('rid', '') for xref in
                    sec.findall('.//xref[@ref-type="fig"]')]
        tbl_refs = [xref.get('rid', '') for xref in
                    sec.findall('.//xref[@ref-type="table"]')]
        sections.append({
            'heading':     heading,
            'text':        '\n\n'.join(p for p in paras if p),
            'figure_refs': fig_refs,
            'table_refs':  tbl_refs,
        })
    return sections


def _extract_figures(root) -> list[dict]:
    figures = []
    for fig in root.findall('.//fig'):
        fig_id  = fig.get('id', '')
        caption = ' '.join(fig.find('caption').itertext()).strip() if fig.find('caption') is not None else ''
        figures.append({
            'fig_id':      fig_id,
            'caption':     caption,
            'coords':      {'page': 1, 'x': 0.0, 'y': 0.0, 'w': 0.0, 'h': 0.0},
            's3_img_key':  '',
            'description': '',
        })
    return figures


def _extract_tables(root) -> list[dict]:
    tables = []
    for tbl_wrap in root.findall('.//table-wrap'):
        tbl_id  = tbl_wrap.get('id', '')
        caption = ' '.join(tbl_wrap.find('caption').itertext()).strip() if tbl_wrap.find('caption') is not None else ''
        tbl_elem = tbl_wrap.find('.//table')
        md = _table_to_markdown(tbl_elem) if tbl_elem is not None else ''
        tables.append({'table_id': tbl_id, 'caption': caption, 'markdown': md})
    return tables


def _table_to_markdown(tbl) -> str:
    rows = tbl.findall('.//tr')
    md_rows = []
    for i, row in enumerate(rows):
        cells = [''.join(c.itertext()).strip() for c in row.findall('td') + row.findall('th')]
        md_rows.append('| ' + ' | '.join(cells) + ' |')
        if i == 0:
            md_rows.append('| ' + ' | '.join(['---'] * len(cells)) + ' |')
    return '\n'.join(md_rows)
