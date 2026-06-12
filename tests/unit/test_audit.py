import json
from datetime import datetime, timezone

from rfe.security.audit import AuditLog
from rfe.security.clock import FixedClock


def test_appends_jsonl_entry(tmp_path):
    path = tmp_path / "audit.jsonl"
    clock = FixedClock(datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc))
    log = AuditLog(str(path), clock=clock)
    log.record("publish", "rubric-1")
    log.record("send", "feedback-9")

    lines = path.read_text().strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first == {"action": "publish", "entity_id": "rubric-1",
                     "timestamp": "2026-01-01T12:00:00+00:00"}


def test_entries_contain_no_pii(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(str(path), clock=FixedClock(datetime(2026, 1, 1, tzinfo=timezone.utc)))
    log.record("approve", "feedback-1")
    entry = json.loads(path.read_text().strip())
    assert set(entry.keys()) == {"action", "entity_id", "timestamp"}


def test_append_only_across_instances(tmp_path):
    path = str(tmp_path / "audit.jsonl")
    clock = FixedClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
    AuditLog(path, clock=clock).record("publish", "r1")
    AuditLog(path, clock=clock).record("delete", "r1")
    lines = open(path).read().strip().splitlines()
    assert [json.loads(l)["action"] for l in lines] == ["publish", "delete"]
