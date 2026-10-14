# Data dictionary (SIST schema)

One row per student, subject and assessment.

| Column | Meaning | Example |
|---|---|---|
| Student_ID | Synthetic ID, or a hashed ID for real data. Never the register number | STU001 |
| Academic_Year | As shown in the ERP | 2025-2026 |
| Term | Exam session | OCT-NOV / APR-MAY |
| Semester | Semester number | 3 |
| Subject_Code | ERP course code | SCSB1303 |
| Subject | Course title | Theory of Computation |
| Assessment | `CAE 1`, `CAE 2`, `Internal`, `Exam` | CAE 1 |
| Marks | Marks obtained | 49 |
| Maximum_Marks | Maximum for that row | 50 |
| Date | Assessment or exam date | 2026-10-12 |

## How the ERP shows marks
- **Current term:** CAE marks, out of 50 per subject (labs out of 25).
- **Past terms:** Internal and Exam marks only. Total = Internal + Exam.
- Percentages are always `Marks / Maximum_Marks`, so rows with different maximums compare fairly.

## Assumptions to confirm
- Theory subjects are 50 internal + 50 exam, labs 25 + 25.
- How CAE marks feed into the Internal mark.
- Credits and the grade scale used for SGPA/CGPA.
