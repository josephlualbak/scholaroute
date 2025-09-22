# ScholaRoute – Smart Student Allocation Platform

**Offline-first, transparent, and merit-based university course allocation system.**

---

## Overview

ScholaRoute automates student allocation to university courses based on grades, subject requirements, and student preferences. It supports up to 3 choices per student, enforces minimum and maximum per-subject scores, computes aggregate scores, and provides fallback placements if none of the preferred choices are eligible. Administrators can also apply manual overrides when necessary.

Outputs include interactive HTML tables, downloadable Excel sheets, and fully formatted PDFs for individual students or full cohorts.

---

## Features

- **Multi-choice Allocation:** Students can select up to 3 preferred courses.
- **Eligibility Checks:** Enforces per-subject minimums and maximums plus aggregate score.
- **Best-fit Fallback:** Allocates students to eligible courses if none of their choices are possible.
- **Manual Overrides:** Admins can override allocations for special cases.
- **Reporting:** Generates HTML tables, Excel exports, and PDFs (full cohort or individual students).
- **Offline-friendly:** Lightweight and works on low-resource environments.
- **Responsive PDF formatting:** Ensures all columns are visible and readable.

---

## Installation

1. Clone the repository:

git clone https://github.com/josephlualbak/scholaroute.git
cd scholaroute

---

## Create a Python virtual environment

python3 -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows

---


## Install dependencies

pip install -r requirements.txt

---

## Usage
1. Prepare Data

students.xlsx: Excel file with student records (ID, Name, Section, subject scores, and Choices 1–3).

universities.json: JSON file containing university courses and min/max score requirements.

2. Start Server
uvicorn api:app --reload --port 8000

Access the frontend at http://127.0.0.1:8000/ in your browser.

3. Allocate Students

Upload the Excel file via the web interface.

Click Allocate Students to generate allocation results.

Preview in-browser or download full PDF/CSV reports.

4. Manual Override

Enter Student ID, University, and Course to apply manual overrides.

Re-run allocation to update results.
