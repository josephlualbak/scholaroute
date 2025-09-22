# schola.py
# ScholaRoute — allocation engine (multi-choice, subject-based, min/max rules, aggregates)

import json
from io import BytesIO
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd
from weasyprint import HTML

# ---------------------------
# Configuration
# ---------------------------

SUBJECTS = [
    "English",
    "Mathematics",
    "Additional Math",
    "Physics",
    "Chemistry",
    "Biology",
    "History",
    "Geography",
    "Civics",
    "ICT",
    "Accounting",
    "Religion",
    "Commerce",
]

COLUMN_ALIASES = {
    "student id": "Student ID",
    "firstname": "FirstName",
    "first name": "FirstName",
    "lastname": "LastName",
    "last name": "LastName",
    "gender": "Gender",
    "section": "Section",
    "choice 1": "Choice 1",
    "choice1": "Choice 1",
    "choice 2": "Choice 2",
    "choice2": "Choice 2",
    "choice 3": "Choice 3",
    "choice3": "Choice 3",
    # subjects
    "english": "English",
    "mathematics": "Mathematics",
    "additional math": "Additional Math",
    "additional mathematics": "Additional Math",
    "add math": "Additional Math",
    "physics": "Physics",
    "chemistry": "Chemistry",
    "biology": "Biology",
    "history": "History",
    "geography": "Geography",
    "civics": "Civics",
    "ict": "ICT",
    "accounting": "Accounting",
    "religion": "Religion",
    "commerce": "Commerce",
}

BASE_CSS = """
body { font-family: Arial, sans-serif; padding: 20px; color: #2c3e50; }
h1 { color: #2c3e50; text-align: center; margin-bottom: 10px; }
h2 { color: #34495e; margin-top: 24px; }
table { width: 100%; border-collapse: collapse; margin-top: 16px; }
th, td { border: 1px solid #ddd; padding: 8px; text-align: center; font-size: 12px; }
th { background-color: #3498db; color: white; }
.small { font-size: 11px; color: #566573; }
.card { border: 1px solid #ccc; padding: 16px; margin-top: 16px; border-radius: 8px; background: #f9f9f9; }
.no-break { page-break-inside: avoid; }
"""

# ---------------------------
# Utilities
# ---------------------------

def _normalize_name(value: str) -> str:
    return (value or "").strip()


def _norm_choice(value: Optional[str]) -> Optional[str]:
    v = (value or "").strip()
    return v if v else None


def _lower(s: str) -> str:
    return (s or "").strip().lower()


def _remap_columns(df: pd.DataFrame) -> pd.DataFrame:
    mapping = {col: COLUMN_ALIASES.get(col.strip().lower(), col) for col in df.columns}
    return df.rename(columns=mapping)


def _collect_choices(row: pd.Series) -> List[str]:
    choices = [_norm_choice(str(row[c])) for c in ["Choice 1", "Choice 2", "Choice 3"] if c in row and pd.notna(row[c])]
    deduped = []
    seen = set()
    for c in choices:
        lc = _lower(c)
        if lc not in seen:
            deduped.append(c)
            seen.add(lc)
    return deduped


def _extract_scores(row: pd.Series) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    for subj in SUBJECTS:
        val = row.get(subj, 0)
        try:
            scores[subj] = float(val) if pd.notna(val) else 0.0
        except Exception:
            scores[subj] = 0.0
    return scores


def _aggregate(scores: Dict[str, float]) -> float:
    # Sum over present subjects, ignoring any NaN values
    total = sum(float(scores.get(s, 0.0) or 0.0) for s in SUBJECTS)
    return round(total, 2)  # rounded for cleaner PDF/HTML display



# ---------------------------
# Allocation session
# ---------------------------

class AllocationSession:
    def __init__(self, universities: Optional[List[dict]] = None):
        self.universities: List[dict] = universities or []
        self.allocations_df: Optional[pd.DataFrame] = None
        self.overrides: Dict[str, Dict[str, str]] = {}

    def load_universities(self, path: str = "universities.json") -> List[dict]:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for uni in data:
            uni["name"] = _normalize_name(uni.get("name", ""))
            for c in uni.get("courses", []):
                c["name"] = _normalize_name(c.get("name", ""))
                c.setdefault("min_scores", {})
                c.setdefault("max_scores", {})
        self.universities = data
        return self.universities

    def is_eligible_for_course(self, scores: Dict[str, float], course: dict) -> bool:
        min_scores: Dict[str, float] = course.get("min_scores", {}) or {}
        max_scores: Dict[str, float] = course.get("max_scores", {}) or {}

        if "aggregate" in min_scores and _aggregate(scores) < float(min_scores["aggregate"]):
            return False

        for subj, min_val in min_scores.items():
            if subj != "aggregate" and scores.get(subj, 0.0) < float(min_val):
                return False
        for subj, max_val in max_scores.items():
            if scores.get(subj, 0.0) > float(max_val):
                return False
        return True

    def best_fit(self, student: dict, scores: Dict[str, float], choices: List[str]) -> Tuple[str, str]:
        sid = _normalize_name(str(student["Student ID"]))
        if sid in self.overrides:
            ov = self.overrides[sid]
            return _normalize_name(ov.get("University", "Manual Override")), _normalize_name(ov.get("Course", "Manual Override"))

        def scan_courses(filter_names: Optional[List[str]] = None) -> Optional[Tuple[str, str]]:
            for uni in self.universities:
                for course in uni.get("courses", []):
                    cname = course.get("name", "")
                    if filter_names and _lower(cname) not in {_lower(c) for c in filter_names}:
                        continue
                    if self.is_eligible_for_course(scores, course):
                        return uni["name"], cname
            return None

        for ch in choices:
            hit = scan_courses([ch])
            if hit:
                return hit

        any_hit = scan_courses(None)
        if any_hit:
            return any_hit

        return "Not Allocated", "N/A"

    def allocate(self, excel_path: str, uni_json_path: str = "universities.json", overrides: Optional[Union[str, Dict[str, Dict[str, str]]]] = None) -> pd.DataFrame:
        if isinstance(overrides, str):
            try:
                overrides = json.loads(overrides)
            except:
                overrides = {}
        self.overrides = overrides or {}
        self.load_universities(uni_json_path)

        df = pd.read_excel(excel_path)
        df = _remap_columns(df)

        core_required = {"Student ID", "FirstName", "LastName", "Gender", "Section"}
        missing_core = [c for c in core_required if c not in df.columns]
        if missing_core:
            raise ValueError(f"Missing required columns: {', '.join(missing_core)}")

        for subj in SUBJECTS:
            if subj not in df.columns:
                df[subj] = 0

        for c in ["Choice 1", "Choice 2", "Choice 3"]:
            if c not in df.columns:
                df[c] = ""

        allocations: List[dict] = []
        for _, row in df.iterrows():
            student = {k: _normalize_name(str(row[k])) for k in ["Student ID", "FirstName", "LastName", "Gender", "Section"]}
            scores = _extract_scores(row)
            agg = _aggregate(scores)
            choices = _collect_choices(row)

            uni, course = self.best_fit(student, scores, choices)

            allocations.append({
                **student,
                **scores,
                "Aggregate": agg,
                "Choice 1": choices[0] if len(choices) > 0 else "",
                "Choice 2": choices[1] if len(choices) > 1 else "",
                "Choice 3": choices[2] if len(choices) > 2 else "",
                "University": uni,
                "Course": course,
            })

        self.allocations_df = pd.DataFrame(allocations)
        return self.allocations_df

    # ---------------------------
    # HTML table rendering (PDF-ready)
    # ---------------------------
    def generate_allocations_table(self) -> str:
        if self.allocations_df is None or self.allocations_df.empty:
            return "<p>No allocations available.</p>"

        # Define the columns in preferred order
        cols = [
            "Student ID", "FirstName", "LastName", "Gender", "Section",
            "Aggregate",
            "Choice 1", "Choice 2", "Choice 3",
            "University", "Course"
        ]
        # Include only columns that exist in the DataFrame
        cols = [c for c in cols if c in self.allocations_df.columns]

        html = ['<div class="table-container"><table>']
        # Header row
        html.append("<tr>" + "".join(f"<th>{c}</th>" for c in cols) + "</tr>")
        # Data rows
        for _, row in self.allocations_df.iterrows():
            html.append("<tr>" + "".join(f"<td>{row.get(c,'')}</td>" for c in cols) + "</tr>")
        html.append("</table></div>")
        return "".join(html)


    def _render_pdf(self, body_html: str) -> BytesIO:
        # Improved CSS for PDF: fixed layout, horizontal scroll, small font
        css = BASE_CSS + """
        .table-container { width: 100%; overflow-x: auto; }
        table { border-collapse: collapse; table-layout: fixed; min-width: 1200px; }
        th, td { border: 1px solid #ccc; padding: 4px 6px; font-size: 10px; word-wrap: break-word; }
        th { background-color: #3498db; color: white; text-align: center; }
        .no-break { page-break-inside: avoid; }
        """
        # Wrap the body HTML in a div with class table-container
        html_content = f"<html><head><style>{css}</style></head><body>{body_html}</body></html>"
        pdf_bytes = HTML(string=html_content).write_pdf()
        return BytesIO(pdf_bytes)



    def generate_student_report(self, student_id: str) -> Optional[BytesIO]:
        if self.allocations_df is None or self.allocations_df.empty:
            return None
        df = self.allocations_df
        student_row = df[df["Student ID"] == student_id]
        if student_row.empty:
            return None
        s = student_row.iloc[0]

        body = f"""
            <h1>ScholaRoute — Student Allocation</h1>
            <div class="card no-break">
                <p><strong>Student ID:</strong> {s['Student ID']}</p>
                <p><strong>Name:</strong> {s['FirstName']} {s['LastName']}</p>
                <p><strong>Gender:</strong> {s['Gender']}</p>
                <p><strong>Section:</strong> {s['Section']}</p>
                <p><strong>Aggregate:</strong> {s.get('Aggregate', '')}</p>
                <p><strong>Choices:</strong> {s.get('Choice 1','')} | {s.get('Choice 2','')} | {s.get('Choice 3','')}</p>
                <p><strong>Allocated University:</strong> {s['University']}</p>
                <p><strong>Allocated Course:</strong> {s['Course']}</p>
            </div>
            <h2>Subject breakdown</h2>
            <table class="no-break">
                <tr>{"".join(f"<th>{subj}</th>" for subj in SUBJECTS)}</tr>
                <tr>{"".join(f"<td>{s.get(subj, 0)}</td>" for subj in SUBJECTS)}</tr>
            </table>
            <p class="small">Allocation is computed against minimum/maximum entry requirements defined by participating universities.</p>
        """
        return self._render_pdf(body)

    def generate_full_pdf(self) -> Optional[BytesIO]:
        if self.allocations_df is None or self.allocations_df.empty:
            return None
        table_html = self.generate_allocations_table()
        body = f"""
            <h1>ScholaRoute — Full Allocations</h1>
            <div class="small">This report summarizes student allocations based on aggregate and subject-specific eligibility, prioritizing choices 1–3 with fallback to best-fit courses.</div>
            {table_html}
        """
        return self._render_pdf(body)
