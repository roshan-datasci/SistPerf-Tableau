# SIST rules used by this project

Source: SIST Academic Regulations 2019, UG B.E./B.Tech. (clause numbers in brackets). Check them against your own batch.

- **Theory:** internal 50 + end-semester 50 [14]. Internal = (CAE 1 + CAE 2, each out of 50, summed out of 100) converted to 40, plus assignments 10 [14.1].
- **Practical:** internal 50 (record 30 + model 20) + end-semester practical 50 [14].
- **End-semester exam** is written for 100 and converted to 50 [14.2].
- **Pass:** at least 50% of total marks and at least 30% of the end-semester marks, otherwise RA (arrear) [15].
- **Grades (out of 100):** 90-100 A++ 10, 80-89 A+ 9, 70-79 B++ 8, 60-69 B+ 7, 50-59 C 6, below 50 RA 0 [16].
- **GPA / CGPA** = sum(credit x grade point) / sum(credit), over courses cleared. RA, AAA and W are excluded [16].
- **Degree class:** CGPA >= 9.0 Exemplary, >= 7.5 Distinction, >= 6.0 First Class, >= 5.0 Second Class. Minimum 5.0 [16, 19].
- **Credits:** total 165 = theory 124 + lab 26 + project 10 + training 5 [10.1]. Per-course credits are not in the ERP marks data: set them in `config.yaml`.
- **Attendance:** 80% for theory and 100% for practicals to sit the end-semester exam [9.1, 14.2].

## What the ERP shows vs. what is estimated
The ERP result table gives Internal, Exam and Total per subject (out of 50 + 50, labs 25 + 25 in your data). Before the Internal mark is published, the dashboard estimates it from your CAEs. If you know your assignment marks, put them in `assignment_marks` in `config.yaml`.
