SAMPLE_TEI = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader>
    <fileDesc>
      <titleStmt>
        <title>Metformin and Renal Function</title>
      </titleStmt>
      <publicationStmt>
        <date type="published" when="2023-06-01"/>
      </publicationStmt>
    </fileDesc>
    <profileDesc>
      <keywords>
        <term>metformin</term>
        <term>renal</term>
      </keywords>
    </profileDesc>
  </teiHeader>
  <text>
    <body>
      <div>
        <head>Introduction</head>
        <p>Metformin is widely used for type 2 diabetes.</p>
      </div>
      <div>
        <head>Methods</head>
        <p>We enrolled 4218 patients.</p>
      </div>
    </body>
  </text>
</TEI>"""


def test_parse_tei_title():
    from modules.module1b_parse.tei_parser import parse_tei

    result = parse_tei(SAMPLE_TEI)
    assert result["title"] == "Metformin and Renal Function"


def test_parse_tei_sections():
    from modules.module1b_parse.tei_parser import parse_tei

    result = parse_tei(SAMPLE_TEI)
    assert len(result["sections"]) == 2
    assert result["sections"][0]["heading"] == "Introduction"
    assert "Metformin" in result["sections"][0]["text"]


def test_parse_tei_pub_date():
    from modules.module1b_parse.tei_parser import parse_tei

    result = parse_tei(SAMPLE_TEI)
    assert result["pub_date"] == "2023-06-01"


def test_parse_tei_keywords():
    from modules.module1b_parse.tei_parser import parse_tei

    result = parse_tei(SAMPLE_TEI)
    assert "metformin" in result["keywords"]
    assert "renal" in result["keywords"]


def test_parse_tei_required_keys():
    from modules.module1b_parse.tei_parser import parse_tei

    result = parse_tei(SAMPLE_TEI)
    for key in (
        "doi",
        "title",
        "abstract",
        "authors",
        "journal",
        "pub_date",
        "sections",
        "figures",
        "tables",
        "keywords",
    ):
        assert key in result, f"Missing key: {key}"
