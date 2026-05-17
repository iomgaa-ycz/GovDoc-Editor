from govdoc.db.models import ActivityLog


def test_activity_log_fields() -> None:
    """验证 ActivityLog 模型字段赋值与读取。"""
    log = ActivityLog(
        actor="user_001",
        action="upload_tender_doc",
        target_type="TenderDoc",
        target_id="abc123",
        before_json=None,
        after_json='{"filename":"test.docx"}',
    )
    assert log.actor == "user_001"
    assert log.action == "upload_tender_doc"
    assert log.target_type == "TenderDoc"
    assert log.target_id == "abc123"
    assert log.before_json is None
    assert log.after_json == '{"filename":"test.docx"}'
