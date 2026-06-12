import pytest

from rfe.adapters.delivery.smtp import SmtpConfig, SmtpDeliverer, build_email_body
from rfe.domain.entities import Candidate, Feedback, FeedbackBullet


def make_candidate() -> Candidate:
    return Candidate(id="c1", role_id="r1", name="Alex", email="alex@x.com",
                     resume_text="resume body")


def make_feedback() -> Feedback:
    return Feedback(id="f1", evaluation_id="e1", candidate_id="c1",
                    intro="Thank you for applying to the SRE role.",
                    bullets=[
                        FeedbackBullet(criterion_id="k8s",
                                       text="The role required 5y Kubernetes; your resume showed 1y."),
                        FeedbackBullet(criterion_id="python",
                                       text="The role required strong Python; limited evidence was found."),
                    ])


class FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout=None):
        self.host, self.port = host, port
        self.started_tls = False
        self.logged_in = None
        self.sent = None
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, user, password):
        self.logged_in = (user, password)

    def send_message(self, msg):
        self.sent = msg


@pytest.fixture(autouse=True)
def _reset():
    FakeSMTP.instances = []


def cfg() -> SmtpConfig:
    return SmtpConfig(host="smtp.local", port=587, user="u", password="p",
                      from_addr="no-reply@x.com")


def test_body_contains_intro_and_bullets():
    body = build_email_body(make_feedback())
    assert "Thank you for applying" in body
    assert "5y Kubernetes" in body
    assert "strong Python" in body


def test_body_has_no_reply_invitation():
    body = build_email_body(make_feedback()).lower()
    for phrase in ("reply", "respond", "get back to us", "let us know"):
        assert phrase not in body


def test_deliver_sends_message_to_candidate():
    deliverer = SmtpDeliverer(cfg(), smtp_factory=FakeSMTP)
    deliverer.deliver(make_candidate(), make_feedback())
    assert len(FakeSMTP.instances) == 1
    smtp = FakeSMTP.instances[0]
    assert smtp.host == "smtp.local" and smtp.port == 587
    assert smtp.started_tls is True
    assert smtp.logged_in == ("u", "p")
    msg = smtp.sent
    assert msg["To"] == "alex@x.com"
    assert msg["From"] == "no-reply@x.com"
    assert "5y Kubernetes" in msg.get_content()


def test_login_skipped_when_no_credentials():
    c = SmtpConfig(host="smtp.local", port=25, user="", password="",
                   from_addr="no-reply@x.com")
    SmtpDeliverer(c, smtp_factory=FakeSMTP).deliver(make_candidate(), make_feedback())
    assert FakeSMTP.instances[0].logged_in is None
