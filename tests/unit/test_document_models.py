"""Document / Tag / DocumentTag 模型单元测试。"""
from datetime import datetime
import uuid

from govdoc.db.models import Document, Tag, DocumentTag


def test_document_defaults():
    doc = Document(filename="test.pdf", file_type="pdf", file_size=1024, sha256="abc123", raw_path="/data/raw/test.pdf")
    assert doc.id is not None
    assert doc.status == "uploading"
    assert doc.markdown_path is None
    assert doc.error_message is None
    assert isinstance(doc.created_at, datetime)
    assert isinstance(doc.updated_at, datetime)


def test_tag_defaults():
    tag = Tag(name="测试标签", color="#DBEAFE:#1D4ED8")
    assert tag.id is not None
    assert tag.name == "测试标签"
    assert isinstance(tag.created_at, datetime)


def test_document_tag_association():
    doc_id = str(uuid.uuid4())
    tag_id = str(uuid.uuid4())
    dt = DocumentTag(document_id=doc_id, tag_id=tag_id)
    assert dt.document_id == doc_id
    assert dt.tag_id == tag_id
