# Observations and throughts from working on projects:

1. The difficulty in maintaining the structure of how a doc is parsed v/s how a human reads/understands it. Keeping them as close as possible.

2. Layout extraction & preservation in PDFs
    - Multi column layouts
    - Single & multi-column sections of a page
    - Headers/footers

3. Specific section / area issues
    - Table parsing properly - Docling does it really well
    - OCR character issue
    - Knowing if the AI summarisation/description of an image/figure is correct
    - Knowing how well an image/figure summary fits in surrounding context
    - Unprintable / out-of-char-set characters
    - Latex forumalae
    - Embedded objects(Visio diagrams etc.) in word docs
    - Webpage XMLs -> Huge dump often without clean separation

4. Document specific
    - Weird issues in Excel - formulae, merged -> Export to PDF and parse
    - PPT structure, objects, speaker notes -> Export to PDF and parse

Custom metrics to compare diff libraries/approaches -
- Section ordering
- Character error rate
- Table parsing correctness
- Image description coherence in adjacent areas
- Spot check

Packages like Docling themselves provide parsing confidence scores. The underlying object detection model classified an area with bonding boxes as text/picture/table. The sigmoid classification prob. of the highest class is the confidence score, not of the text within.

For the bboxes below a threshold, they can be resent to an LLM for re-parsing or it can be analysed separately.

No parsing library, technique is perfect. In my experience Docling is currently the industry standard, it does mostly well. It falters on multi-column and formulae sometimes. Images/OCR are outsourced for inline description through VLM/OCR models. It does exceptionally well w.r.t. tables. It is also undergoing a lot of active development, so it is a good library to build on.
