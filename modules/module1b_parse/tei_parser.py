from lxml import etree

NS = {"tei": "http://www.tei-c.org/ns/1.0"}


def parse_tei(tei_xml: str) -> dict:
    root = etree.fromstring(tei_xml.encode())
    return {
        "doi": _extract_doi(root),
        "title": root.findtext(".//tei:titleStmt/tei:title", namespaces=NS) or "",
        "abstract": " ".join(
            p.text or "" for p in root.findall(".//tei:abstract//tei:p", namespaces=NS)
        ),
        "authors": _extract_authors(root),
        "journal": root.findtext('.//tei:monogr/tei:title[@level="j"]', namespaces=NS) or "",
        "pub_date": _extract_pub_date(root),
        "mesh_terms": [],
        "keywords": [
            k.text for k in root.findall(".//tei:keywords/tei:term", namespaces=NS) if k.text
        ],
        "sections": _extract_sections(root),
        "figures": _extract_figures(root),
        "tables": _extract_tables(root),
    }


def _extract_doi(root) -> str:
    for idno in root.findall(".//tei:idno", namespaces=NS):
        if idno.get("type", "").upper() == "DOI" and idno.text:
            return str(idno.text).strip()
    return ""


def _extract_authors(root) -> list[dict]:
    authors = []
    for author in root.findall(".//tei:fileDesc//tei:author", namespaces=NS):
        persname = author.find("tei:persName", namespaces=NS)
        if persname is None:
            continue
        forename = persname.findtext("tei:forename", namespaces=NS, default="")
        surname = persname.findtext("tei:surname", namespaces=NS, default="")
        affil = author.findtext(".//tei:affiliation/tei:orgName", namespaces=NS, default="")
        name = f"{forename} {surname}".strip()
        if name:
            authors.append({"name": name, "affiliation": affil})
    return authors


def _extract_pub_date(root) -> str:
    date_elem = root.find('.//tei:publicationStmt/tei:date[@type="published"]', namespaces=NS)
    if date_elem is not None:
        when = str(date_elem.get("when", ""))
        if when:
            return when[:10]  # YYYY-MM-DD
    return ""


def _extract_sections(root) -> list[dict]:
    sections = []
    for div in root.findall(".//tei:body/tei:div", namespaces=NS):
        heading = div.findtext("tei:head", namespaces=NS, default="")
        paras = [
            p.text_content() if hasattr(p, "text_content") else (p.text or "")
            for p in div.findall("tei:p", namespaces=NS)
        ]
        fig_refs = [
            r.get("target", "").lstrip("#")
            for r in div.findall('.//tei:ref[@type="figure"]', namespaces=NS)
        ]
        tbl_refs = [
            r.get("target", "").lstrip("#")
            for r in div.findall('.//tei:ref[@type="table"]', namespaces=NS)
        ]
        sections.append(
            {
                "heading": heading,
                "text": "\n\n".join(paras),
                "figure_refs": fig_refs,
                "table_refs": tbl_refs,
            }
        )
    return sections


def _extract_figures(root) -> list[dict]:
    figures = []
    for fig in root.findall(".//tei:figure", namespaces=NS):
        if fig.get("type") == "table":
            continue
        fig_id = fig.get("{http://www.w3.org/XML/1998/namespace}id", "") or fig.get("xml:id", "")
        caption = fig.findtext(".//tei:figDesc", namespaces=NS, default="")
        coords = _parse_coords(fig.get("coords", ""))
        figures.append(
            {
                "fig_id": fig_id,
                "caption": caption,
                "coords": coords,
                "s3_img_key": "",
                "description": "",
            }
        )
    return figures


def _extract_tables(root) -> list[dict]:
    tables = []
    for fig in root.findall('.//tei:figure[@type="table"]', namespaces=NS):
        tbl_id = fig.get("{http://www.w3.org/XML/1998/namespace}id", "")
        caption = fig.findtext(".//tei:figDesc", namespaces=NS, default="")
        table_elem = fig.find(".//tei:table", namespaces=NS)
        md = _table_to_markdown(table_elem) if table_elem is not None else ""
        tables.append({"table_id": tbl_id, "caption": caption, "markdown": md})
    return tables


def _parse_coords(coords_str: str) -> dict:
    """Parse Grobid coords string 'page,x,y,w,h' into a dict."""
    if not coords_str:
        return {"page": 1, "x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0}
    parts = coords_str.split(",")
    if len(parts) >= 5:
        return {
            "page": int(parts[0]),
            "x": float(parts[1]),
            "y": float(parts[2]),
            "w": float(parts[3]),
            "h": float(parts[4]),
        }
    return {"page": 1, "x": 0.0, "y": 0.0, "w": 0.0, "h": 0.0}


def _table_to_markdown(table_elem) -> str:
    rows = table_elem.findall(".//tei:row", namespaces=NS)
    md_rows = []
    for i, row in enumerate(rows):
        cells = [
            c.text_content().strip() if hasattr(c, "text_content") else (c.text or "")
            for c in row.findall("tei:cell", namespaces=NS)
        ]
        md_rows.append("| " + " | ".join(cells) + " |")
        if i == 0:
            md_rows.append("| " + " | ".join(["---"] * len(cells)) + " |")
    return "\n".join(md_rows)
