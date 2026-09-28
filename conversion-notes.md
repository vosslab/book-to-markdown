# Conversion evidence: The Self-Service Data Roadmap

- Source: `/Volumes/Ex2GB/books/ORIGINAL_SOURCES/15_Assorted_Computers_and_Technology_Books_Collection_Pack_1_FreeBooksOnline.top/The_Self-Service_Data_Roadmap/The_Self-Service_Data_Roadmap.epub`
- Source SHA-256: `427c212730348d1631c6774c76fbead95358504d6720c2c53feaa617872185ad`
- EPUB metadata: Sandeep Uttamchandani, O'Reilly Media, ISBN 9781492075257; metadata date 2019-12-23.
- Extraction route: Pandoc 3.11 EPUB reader to standalone Markdown, with media extracted into the visible sibling `media/` directory. This reads EPUB text in its packaged order and retains code, headings, captions, index, and illustrations.
- Candidate: `The_Self-Service_Data_Roadmap-2019.md`.
- Structure coverage observed: front matter, 18 numbered chapters, index, author biography, and colophon. The extraction produced 92 media files.
- Repository structure inspection: `extract/epub_structure.py` could not inspect the source because its secure XML parser rejects a `DOCTYPE` declaration in `OEBPS/toc01.xhtml`. No source modification was made.
- Validator outcomes: `validate_markdown_v2.py` FAIL, 5 issues (one H1-count issue, non-ASCII content, image markup in two locations, and disallowed `section` HTML). `validate_markdown_delivery.py` FAIL, 7 issues (one H1-count issue, image markup/active HTML, and non-ASCII content). Machine-readable reports are alongside this note.
- Unresolved source/conversion details: EPUB metadata date is 2019, while its copyright page says copyright 2020 and September 2020 first edition. Proposed canonical filename follows the assigned 2019 metadata year. Pandoc preserves many chapter headings as H1 and emits figure/cover image markup and some raw HTML; validators therefore fail. Review those transformations and the year before promotion.
