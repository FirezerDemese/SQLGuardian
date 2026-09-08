"""
Generate the binary sample runbooks (.docx and .pdf).

The Markdown, text and HTML samples in docs/runbook-samples are written by hand.
The two binary formats are generated here so the content stays reviewable in
source control and so anyone can regenerate them:

    python scripts/make_sample_runbooks.py

DOCX uses python-docx, which is already a dependency because the ingestion
pipeline reads .docx. The PDF is written directly rather than pulling in a PDF
authoring library that nothing else in the project would use - it is a minimal
single-font PDF, which is exactly what pypdf has to be able to read anyway.
"""

from __future__ import annotations

import sys
from pathlib import Path

SAMPLES = Path(__file__).resolve().parent.parent / "docs" / "runbook-samples"


# ---------------------------------------------------------------------------
# DOCX - wait statistics triage
# ---------------------------------------------------------------------------

DOCX_CONTENT: list[tuple[str, str]] = [
    ("Heading 1", "Wait Statistics Triage"),
    ("Normal", "Owner: Platform Data Engineering. Escalation: #db-oncall. "
               "Last reviewed: 2026-04-30."),
    ("Heading 2", "Instance dominated by a single wait type"),
    ("Normal", "Conditions: WAIT_SPIKE"),
    ("Normal", "Applies when one wait type accounts for most of the wait time in a "
               "sampling window. Cumulative wait totals since restart are not an "
               "incident signal and must not be triaged with this procedure."),
    ("List Number", "Identify the sessions currently waiting on that type before "
                    "reading anything into the aggregate. Aggregates tell you what to "
                    "look at, not what is wrong."),
    ("List Number", "For LCK_ waits, stop here and follow the blocking chain "
                    "procedure. Lock waits are a contention incident, not a tuning one."),
    ("List Number", "For PAGEIOLATCH_SH or WRITELOG, check storage latency with the "
                    "Infrastructure dashboard before touching any query. If latency is "
                    "above 20ms this is a storage incident and belongs to Infrastructure."),
    ("List Number", "For RESOURCE_SEMAPHORE, look for a query with an oversized memory "
                    "grant. Do not raise max server memory during the incident."),
    ("List Number", "For THREADPOOL, treat it as a symptom of blocking, not a "
                    "configuration problem. Raising max worker threads hides it."),
    ("List Number", "Record a baseline before making any change so the effect can be "
                    "measured afterwards."),
    ("Normal", "Rollback: this procedure is diagnostic only. Nothing in it changes "
               "server state, so there is nothing to roll back."),
]


def write_docx(path: Path) -> None:
    import docx

    document = docx.Document()
    for style, text in DOCX_CONTENT:
        document.add_paragraph(text, style=style)
    document.save(str(path))
    print(f"wrote {path}")


# ---------------------------------------------------------------------------
# PDF - on-call escalation quick reference
# ---------------------------------------------------------------------------

PDF_LINES: list[str] = [
    "PLATFORM DATA ENGINEERING",
    "ON-CALL ESCALATION QUICK REFERENCE",
    "",
    "Last reviewed: 2026-07-02. Print this. It is the page you want at 03:00.",
    "",
    "SEVERITY DEFINITIONS",
    "",
    "P1  Service is down, or data loss is possible. Page the duty manager",
    "    immediately. Do not triage first.",
    "P2  Service is degraded for users, or a Tier 1 database is unprotected.",
    "    Declare in #incident, then triage.",
    "P3  Contained, no user impact yet. Handle in hours.",
    "",
    "TIER 1 DATABASES",
    "",
    "WideWorldImporters, OrderPlatform. RPO 15 minutes, RTO 1 hour.",
    "Anything affecting recoverability of these two is a P2 minimum.",
    "",
    "CONTACTS",
    "",
    "Database on-call        #db-oncall",
    "Duty manager            rota in the on-call calendar",
    "Fulfilment on-call      #fulfilment-oncall (OrderSync, WMS-Bridge)",
    "Integration team        #integration (replication, log reader)",
    "Infrastructure          #infra-oncall (SAN, storage extension, hypervisor)",
    "",
    "RULES THAT DO NOT CHANGE",
    "",
    "No destructive action on a production instance without a second person",
    "on the call. No exceptions during an incident, and no exceptions for",
    "anything that cannot be undone.",
]


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def write_pdf(path: Path, lines: list[str] | None = None) -> None:
    """A minimal, valid, single-font PDF with extractable text.

    `lines` is overridable so tests can build a valid PDF that contains no text,
    which is how a scanned, image-only runbook behaves.
    """
    content = PDF_LINES if lines is None else lines
    lines_per_page = 30
    pages = [
        content[i : i + lines_per_page] for i in range(0, len(content), lines_per_page)
    ] or [[]]

    objects: list[bytes] = []

    def add(obj: bytes) -> int:
        objects.append(obj)
        return len(objects)  # 1-based object number

    # Reserve 1 (catalog) and 2 (pages tree); font is 3.
    objects.append(b"")  # placeholder for catalog
    objects.append(b"")  # placeholder for pages tree
    font_num = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier >>")

    page_nums: list[int] = []
    for page_lines in pages:
        stream_parts = ["BT", "/F1 11 Tf", "14 TL", "56 760 Td"]
        for line in page_lines:
            stream_parts.append(f"({_escape(line)}) Tj T*")
        stream_parts.append("ET")
        stream = "\n".join(stream_parts).encode("latin-1", "replace")
        content_num = add(
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
        )
        page_num = add(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Resources << /Font << /F1 " + str(font_num).encode() + b" 0 R >> >> "
            b"/Contents " + str(content_num).encode() + b" 0 R >>"
        )
        page_nums.append(page_num)

    kids = b" ".join(f"{n} 0 R".encode() for n in page_nums)
    objects[1] = (
        b"<< /Type /Pages /Kids [" + kids + b"] /Count " + str(len(page_nums)).encode() + b" >>"
    )
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"

    out = bytearray(b"%PDF-1.4\n")
    offsets: list[int] = []
    for index, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{index} 0 obj\n".encode() + body + b"\nendobj\n"

    xref_offset = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n"
    ).encode()
    out += b"%%EOF\n"

    path.write_bytes(bytes(out))
    print(f"wrote {path}")


def main() -> int:
    SAMPLES.mkdir(parents=True, exist_ok=True)
    write_docx(SAMPLES / "wait-stats-triage.docx")
    write_pdf(SAMPLES / "oncall-escalation-quick-reference.pdf")
    return 0


if __name__ == "__main__":
    sys.exit(main())
