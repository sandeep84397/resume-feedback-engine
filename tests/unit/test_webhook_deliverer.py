import hashlib
import hmac
import json

import httpx
import pytest

from rfe.adapters.delivery.webhook import WebhookDeliverer
from rfe.domain.entities import Candidate, Feedback, FeedbackBullet


def make_candidate() -> Candidate:
    return Candidate(id="c1", role_id="r1", name="A", email="a@x.com",
                     resume_text="resume body")


def make_feedback() -> Feedback:
    return Feedback(id="f1", evaluation_id="e1", candidate_id="c1", intro="Hi",
                    bullets=[FeedbackBullet(criterion_id="k8s", text="...")])


def make_deliverer(handler, secret="whsecret") -> WebhookDeliverer:
    client = httpx.Client(transport=httpx.MockTransport(handler),
                          base_url="http://hook.local")
    return WebhookDeliverer(client=client, url="http://hook.local/in", secret=secret)


def test_posts_signed_payload():
    seen = {}

    def handler(request):
        seen["sig"] = request.headers.get("X-RFE-Signature")
        seen["body"] = request.content
        return httpx.Response(200, json={"ok": True})

    make_deliverer(handler).deliver(make_candidate(), make_feedback())

    expected = hmac.new(b"whsecret", seen["body"], hashlib.sha256).hexdigest()
    assert seen["sig"] == expected
    payload = json.loads(seen["body"])
    assert payload["feedback_id"] == "f1"
    assert payload["candidate_id"] == "c1"
    assert payload["bullets"][0]["criterion_id"] == "k8s"


def test_non_2xx_raises():
    deliverer = make_deliverer(lambda r: httpx.Response(500, text="boom"))
    with pytest.raises(Exception):
        deliverer.deliver(make_candidate(), make_feedback())
