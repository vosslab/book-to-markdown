# Related projects

`book-to-markdown` gives technical and scientific book converters a staged path from source files
to one reviewed, page-free Markdown deliverable.

## Confirmed related projects

### Pandoc

- Relationship: companion/interoperability tool
- Link: [Pandoc](https://pandoc.org/)
- Why visitors may care: Pandoc converts EPUB, DOCX, HTML, ODT, and other structured formats to
  Markdown, and can provide a clean structural starting point before this repository's cleanup and
  validation stages.
- Evidence: This repository ships `extract/semantic_markdown.lua`, a Pandoc filter. Pandoc's
  official format list documents EPUB, DOCX, HTML, ODT, and Markdown conversion support.

## Possible related projects

### Docling

- Relationship: direct alternative
- Link: [Docling](https://docling-project.github.io/docling/)
- Why visitors may care: Docling converts digital and scanned PDFs to Markdown, including OCR
  handling, when a visitor needs a different PDF extraction engine.
- Evidence: Docling's official quickstart documents local PDF conversion and Markdown export.
- Confidence: likely

### Marker

- Relationship: direct alternative
- Link: [Marker](https://github.com/VikParuchuri/marker)
- Why visitors may care: Marker converts PDF, EPUB, and MOBI books to Markdown and targets
  scientific documents, tables, equations, and header/footer removal.
- Evidence: The project's official repository describes those source formats and features.
- Confidence: likely

### Calibre ebook-convert

- Relationship: same-workflow implementation
- Link: [Calibre ebook-convert](https://manual.calibre-ebook.com/en/generated/en/ebook-convert.html)
- Why visitors may care: Calibre can make Markdown-formatted text from a supported ebook input,
  offering a separate starting point for ebook conversion.
- Evidence: Calibre's official CLI documentation identifies `ebook-convert` as an ebook converter
  and documents Markdown as a text-output formatting choice.
- Confidence: possible

## Evidence notes

Pandoc is a confirmed companion because this repository includes its Lua filter. The remaining
entries are possible alternatives based on each project's official format and conversion
documentation; none has an upstream, fork, or shared-maintainer relationship with this repository.
