"""
Minimal MCP server with PDF tools:
  - make_pdf: generates a simple PDF from title/body text, saves it, returns a link
  - list_pdfs: lists PDF files you've placed in the pdfs/ folder
  - get_pdf_link: returns a downloadable HTTPS link to one of your own PDF files

Run locally over stdio:
    python server.py

Or run remotely over HTTP (Streamable HTTP transport):
    python server.py --http
"""

import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from starlette.responses import FileResponse, JSONResponse

mcp = FastMCP(
    "pdf-server",
    host="0.0.0.0",
    port=int(os.environ.get("PORT", 8000)),
)

# Drop your own PDF files in this folder (next to server.py).
PDFS_DIR = Path(__file__).parent / "pdfs"
PDFS_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# IMPORTANT: set this to your actual public Render URL (no trailing slash).
# You can also set it via the BASE_URL environment variable in Render's
# dashboard instead of hardcoding it here.
# ---------------------------------------------------------------------------
BASE_URL = os.environ.get("BASE_URL", "https://mcp-server-demo-0qr5.onrender.com")


def _build_pdf(title: str, body: str) -> bytes:
    from io import BytesIO

    buf = BytesIO()
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


def _safe_pdf_path(filename: str) -> Path:
    """Resolve filename inside PDFS_DIR only — blocks path traversal like '../'."""
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    path = (PDFS_DIR / filename).resolve()
    if PDFS_DIR.resolve() not in path.parents and path != PDFS_DIR.resolve():
        raise ValueError("Invalid filename.")
    return path


# ---------------------------------------------------------------------------
# Plain HTTP route that actually serves the file bytes.
# This lives on the same Starlette app as the MCP endpoint, so no extra
# hosting or port config is needed — Render exposes it automatically at
# BASE_URL + "/files/<name>.pdf".
# ---------------------------------------------------------------------------
@mcp.custom_route("/files/{filename}", methods=["GET"])
async def serve_pdf(request):
    filename = request.path_params["filename"]
    try:
        path = _safe_pdf_path(filename)
    except ValueError:
        return JSONResponse({"error": "invalid filename"}, status_code=400)
    if not path.exists():
        return JSONResponse({"error": "not found"}, status_code=404)
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@mcp.tool()
def make_pdf(title: str, body: str, filename: str = "report.pdf") -> str:
    """
    Generate a PDF document, save it to the server, and return a link to it.

    Args:
        title: Heading text for the PDF.
        body: Plain text content (newlines become new lines in the PDF).
        filename: Name to save the file as, e.g. "report.pdf" (extension optional).
    """
    pdf_bytes = _build_pdf(title, body)
    path = _safe_pdf_path(filename)
    path.write_bytes(pdf_bytes)
    return f"{BASE_URL}/files/{path.name}"


@mcp.tool()
def list_pdfs() -> str:
    """List the PDF files available on the server (in the pdfs/ folder)."""
    names = sorted(p.name for p in PDFS_DIR.glob("*.pdf"))
    if not names:
        return "No PDFs found. Add files to the pdfs/ folder next to server.py."
    return "\n".join(names)


@mcp.tool()
def get_pdf_link(filename: str) -> str:
    """
    Return a downloadable HTTPS link to one of your own PDF files.

    Args:
        filename: Name of the file, e.g. "resume.pdf" (extension optional).
    """
    path = _safe_pdf_path(filename)
    if not path.exists():
        raise FileNotFoundError(
            f"'{filename}' not found in pdfs/. Use list_pdfs to see what's available."
        )
    return f"{BASE_URL}/files/{path.name}"


if __name__ == "__main__":
    if "--http" in sys.argv:
        # Streamable HTTP transport for remote hosting.
        # Exposes the MCP endpoint at http://<host>:<port>/mcp
        # and the file route at http://<host>:<port>/files/<name>.pdf
        mcp.run(transport="streamable-http")
    else:
        # stdio transport — used for local Claude Desktop connections.
        mcp.run()
