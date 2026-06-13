import base64

from fastapi.testclient import TestClient

from rfe.adapters.llm.mock import MockModelProvider
from rfe.api.app import build_app


def client() -> TestClient:
    return TestClient(build_app(model_provider=MockModelProvider([])))


def simple_pdf_bytes(text: str) -> bytes:
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n"
        + stream + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, 1):
        offsets.append(len(pdf))
        pdf.extend(f"{i} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref_at = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode())
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF\n".encode()
    )
    return bytes(pdf)


def test_extracts_text_from_pdf_resume():
    encoded = base64.b64encode(simple_pdf_bytes("Jane Resume Python")).decode()

    resp = client().post("/resume/extract", json={
        "filename": "resume.pdf",
        "content_base64": encoded,
    })

    assert resp.status_code == 200
    assert "Jane Resume Python" in resp.json()["text"]


def test_rejects_unsupported_resume_file_type():
    encoded = base64.b64encode(b"hello").decode()

    resp = client().post("/resume/extract", json={
        "filename": "resume.docx",
        "content_base64": encoded,
    })

    assert resp.status_code == 422


def test_rejects_large_resume_upload():
    encoded = base64.b64encode(b"x" * (2_000_001)).decode()

    resp = client().post("/resume/extract", json={
        "filename": "resume.pdf",
        "content_base64": encoded,
    })

    assert resp.status_code == 422
