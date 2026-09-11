"""
Minimal MCP server with PDF tools:
  - make_pdf: generates a simple PDF from title/body text
  - list_pdfs: lists PDF files you've placed in the pdfs/ folder
  - get_pdf: returns one of your own PDF files by name

Run locally over stdio:
    python server.py

Or run remotely over HTTP (Streamable HTTP transport):
    python server.py --http
"""

import base64
import io
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import mcp.types as types

mcp = FastMCP(
    "pdf-server",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 8000)),
)

# Drop your own PDF files in this folder (next to server.py).
PDFS_DIR = Path(__file__).parent / "pdfs"
PDFS_DIR.mkdir(exist_ok=True)


def _build_pdf(title: str, body: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=letter)
    width, height = letter

    c.setFont("Helvetica-Bold", 18)
    c.drawString(72, height - 72, title)

    c.setFont("Helvetica", 11)
    y = height - 110
    for line in body.splitlines() or [""]:
        c.drawString(72, y, line)
        y -= 16
        if y < 72:
            c.showPage()
            y = height - 72

    c.save()
    buf.seek(0)
    return buf.read()


def _pdf_resource(pdf_bytes: bytes, name: str) -> list[types.EmbeddedResource]:
    b64 = base64.b64encode(pdf_bytes).decode("ascii")
    return [
        types.EmbeddedResource(
            type="resource",
            resource=types.BlobResourceContents(
                uri=f"pdf://generated/{name}",
                mimeType="application/pdf",
                blob=b64,
            ),
        )
    ]


def _safe_pdf_path(filename: str) -> Path:
    """Resolve filename inside PDFS_DIR only — blocks path traversal like '../'."""
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    path = (PDFS_DIR / filename).resolve()
    if PDFS_DIR.resolve() not in path.parents and path != PDFS_DIR.resolve():
        raise ValueError("Invalid filename.")
    return path


@mcp.tool()
def make_pdf(title: str, body: str) -> list[types.EmbeddedResource]:
    """
    Generate a PDF document and return it to the client.

    Args:
        title: Heading text for the PDF.
        body: Plain text content (newlines become new lines in the PDF).
    """
    pdf_bytes = _build_pdf(title, body)
    return _pdf_resource(pdf_bytes, "report.pdf")


@mcp.tool()
def list_pdfs() -> str:
    """List the PDF files available on the server (in the pdfs/ folder)."""
    names = sorted(p.name for p in PDFS_DIR.glob("*.pdf"))
    if not names:
        return "No PDFs found. Add files to the pdfs/ folder next to server.py."
    return "\n".join(names)


@mcp.tool()
def get_pdf(filename: str) -> list[types.EmbeddedResource]:
    """
    Return one of your own PDF files from the pdfs/ folder.

    Args:
        filename: Name of the file, e.g. "resume.pdf" (extension optional).
    """
    path = _safe_pdf_path(filename)
    if not path.exists():
        raise FileNotFoundError(
            f"'{filename}' not found in pdfs/. Use list_pdfs to see what's available."
        )
    return _pdf_resource(path.read_bytes(), path.name)


if __name__ == "__main__":
    if "--http" in sys.argv:
        # Streamable HTTP transport for remote hosting.
        # Exposes the server at http://<host>:<port>/mcp
        mcp.run(transport="streamable-http")
    else:
        # stdio transport — used for local Claude Desktop connections.
        mcp.run()
