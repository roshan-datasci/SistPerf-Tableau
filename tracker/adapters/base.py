class Adapter:
    """A data source. fetch() returns rows with the SistPerf columns:
    Student_ID, Academic_Year, Term, Semester, Subject_Code, Subject, Assessment, Marks, Maximum_Marks, Date"""
    def fetch(self):
        raise NotImplementedError
