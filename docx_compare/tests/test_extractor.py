from __future__ import annotations

from pathlib import Path
import unittest
import zipfile

from docx_common_text.extractor import extract_docx_paragraphs


CONTENT_TYPES_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
  <Default Extension="xml" ContentType="application/xml"/>
  <Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>
"""

RELS_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>
"""

DOCUMENT_XML = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
  <w:body>
    <w:p><w:r><w:t>First paragraph.</w:t></w:r></w:p>
    <w:tbl>
      <w:tr>
        <w:tc>
          <w:p><w:r><w:t>Table cell text.</w:t></w:r></w:p>
        </w:tc>
      </w:tr>
    </w:tbl>
    <w:p><w:r><w:t>Last paragraph.</w:t></w:r></w:p>
    <w:sectPr />
  </w:body>
</w:document>
"""


def build_minimal_docx(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("[Content_Types].xml", CONTENT_TYPES_XML)
        archive.writestr("_rels/.rels", RELS_XML)
        archive.writestr("word/document.xml", DOCUMENT_XML)


class ExtractorTests(unittest.TestCase):
    def test_extract_docx_paragraphs_reads_paragraphs_and_tables(self) -> None:
        artifacts_dir = Path.cwd() / "tests" / "_artifacts"
        artifacts_dir.mkdir(exist_ok=True)
        docx_path = artifacts_dir / "sample.docx"

        build_minimal_docx(docx_path)
        paragraphs = extract_docx_paragraphs(docx_path)

        self.assertEqual(
            paragraphs,
            ["First paragraph.", "Table cell text.", "Last paragraph."],
        )


if __name__ == "__main__":
    unittest.main()
