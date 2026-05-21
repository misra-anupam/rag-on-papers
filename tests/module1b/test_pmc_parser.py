import pytest

SAMPLE_PMC_XML = b'''<?xml version="1.0"?>
<article>
  <front>
    <journal-meta>
      <journal-title-group>
        <journal-title>Diabetes Care</journal-title>
      </journal-title-group>
    </journal-meta>
    <article-meta>
      <article-id pub-id-type="doi">10.2337/dc23-0441</article-id>
      <title-group>
        <article-title>Long-term Renal Effects of Metformin</article-title>
      </title-group>
      <contrib-group>
        <contrib contrib-type="author">
          <name>
            <surname>Smith</surname>
            <given-names>Jane</given-names>
          </name>
        </contrib>
      </contrib-group>
      <pub-date pub-type="epub">
        <year>2023</year><month>6</month><day>1</day>
      </pub-date>
      <abstract><p>This study examined renal outcomes with metformin.</p></abstract>
    </article-meta>
  </front>
  <body>
    <sec>
      <title>Introduction</title>
      <p>Metformin is the recommended first-line drug.</p>
    </sec>
    <sec>
      <title>Methods</title>
      <p>We used a cohort of 4218 patients.</p>
    </sec>
  </body>
</article>'''


def test_pmc_doi():
    from modules.module1b_parse.pmc_parser import parse_pmc_xml
    result = parse_pmc_xml(SAMPLE_PMC_XML)
    assert result['doi'] == '10.2337/dc23-0441'


def test_pmc_title():
    from modules.module1b_parse.pmc_parser import parse_pmc_xml
    result = parse_pmc_xml(SAMPLE_PMC_XML)
    assert 'Metformin' in result['title']


def test_pmc_pub_date():
    from modules.module1b_parse.pmc_parser import parse_pmc_xml
    result = parse_pmc_xml(SAMPLE_PMC_XML)
    assert result['pub_date'].startswith('2023')


def test_pmc_sections():
    from modules.module1b_parse.pmc_parser import parse_pmc_xml
    result = parse_pmc_xml(SAMPLE_PMC_XML)
    headings = [s['heading'] for s in result['sections']]
    assert 'Introduction' in headings
    assert 'Methods' in headings


def test_pmc_schema_matches_tei():
    """Both parsers must return the same top-level keys."""
    from modules.module1b_parse.pmc_parser import parse_pmc_xml
    from modules.module1b_parse.tei_parser import parse_tei
    from tests.module1b.test_tei_parser import SAMPLE_TEI

    pmc_result = parse_pmc_xml(SAMPLE_PMC_XML)
    tei_result = parse_tei(SAMPLE_TEI)

    assert set(pmc_result.keys()) == set(tei_result.keys()), (
        f'Schema mismatch. PMC extra: {set(pmc_result.keys()) - set(tei_result.keys())}, '
        f'TEI extra: {set(tei_result.keys()) - set(pmc_result.keys())}'
    )
