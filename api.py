# api.py
import os
from typing import Optional

from fastapi import FastAPI, UploadFile, File, Form, Request, HTTPException
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette import status

import schola

# ----------------------
# App and path settings
# ----------------------
app = FastAPI(title="ScholaRoute API", version="3.0.0")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
DATA_DIR = os.path.join(BASE_DIR, "data")

os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# ----------------------
# In-memory state
# ----------------------
app.state.session: Optional[schola.AllocationSession] = None
app.state.last_excel_path: Optional[str] = None
app.state.universities_path: str = os.path.join(BASE_DIR, "universities.json")


# ------------
# UI endpoint
# ------------
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# -----------------------
# Allocation + HTML table
# -----------------------
@app.post("/allocate", response_class=HTMLResponse)
async def allocate_students(file: UploadFile = File(...)):
    contents = await file.read()
    excel_path = os.path.join(DATA_DIR, "uploaded_students.xlsx")
    with open(excel_path, "wb") as f:
        f.write(contents)

    session = schola.AllocationSession()
    try:
        df_alloc = session.allocate(
            excel_path=excel_path,
            uni_json_path=app.state.universities_path,
            overrides=session.overrides
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Allocation failed: {e}")

    app.state.session = session
    app.state.last_excel_path = excel_path

    html_table = session.generate_allocations_table()
    return HTMLResponse(content=html_table, status_code=status.HTTP_200_OK)


# -----------------
# Apply an override
# -----------------
@app.post("/override")
async def override_allocation(
    student_id: str = Form(...),
    university: str = Form(...),
    course: str = Form(...)
):
    if not app.state.last_excel_path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No uploaded data to override yet.")

    session = app.state.session or schola.AllocationSession()
    overrides = session.overrides or {}
    overrides[str(student_id).strip()] = {"University": university.strip(), "Course": course.strip()}

    try:
        session.allocate(
            excel_path=app.state.last_excel_path,
            uni_json_path=app.state.universities_path,
            overrides=overrides
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Re-allocation failed: {e}")

    app.state.session = session
    return JSONResponse({"status": "override applied", "student_id": student_id})


# -----------------------------
# Download: full allocations PDF
# -----------------------------
@app.get("/download_allocations/pdf")
async def download_allocations_pdf():
    session = app.state.session
    if session is None or session.allocations_df is None or session.allocations_df.empty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No allocations available.")

    pdf_bytes = session.generate_full_pdf()
    if not pdf_bytes:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate PDF.")

    pdf_path = os.path.join(DATA_DIR, "allocations_full.pdf")
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes.getvalue())

    return FileResponse(pdf_path, media_type="application/pdf", filename="allocations_full.pdf")


# -----------------------------------
# Download: per-student allocation PDF
# -----------------------------------
@app.get("/download_report/{student_id}")
async def download_student_report(student_id: str):
    session = app.state.session
    if session is None or session.allocations_df is None or session.allocations_df.empty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No allocations available.")

    pdf_bytes = session.generate_student_report(student_id)
    if not pdf_bytes:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")

    pdf_path = os.path.join(DATA_DIR, f"student_{student_id}.pdf")
    with open(pdf_path, "wb") as f:
        f.write(pdf_bytes.getvalue())

    return FileResponse(pdf_path, media_type="application/pdf", filename=f"student_{student_id}.pdf")


# ---------------------------
# Optional: allocations as CSV
# ---------------------------
@app.get("/download_allocations/csv")
async def download_allocations_csv():
    session = app.state.session
    if session is None or session.allocations_df is None or session.allocations_df.empty:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No allocations available.")

    csv_path = os.path.join(DATA_DIR, "allocations.csv")
    session.allocations_df.to_csv(csv_path, index=False)

    return FileResponse(csv_path, media_type="text/csv", filename="allocations.csv")


# ---------------------------
# Healthcheck
# ---------------------------
@app.get("/health")
async def health():
    has_session = app.state.session is not None
    has_allocations = has_session and app.state.session.allocations_df is not None and not app.state.session.allocations_df.empty
    return {"status": "ok", "session": has_session, "allocations_loaded": bool(has_allocations)}
