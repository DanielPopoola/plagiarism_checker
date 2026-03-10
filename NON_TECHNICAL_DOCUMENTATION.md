# User Guide

This document explains how to use the plagiarism detection system. No technical knowledge is required.

---

## What This System Does

When students submit written assignments or take-home exam answers, it can be difficult to manually check whether any of them copied from each other. This system handles that automatically.

Here is what happens, from start to finish:

1. A lecturer creates an exam and sets a submission window (open date and close date)
2. Students log in, find the exam, and upload their written work as a file
3. The system stores the submission and immediately begins comparing it against all other submissions for the same exam
4. Once the window closes, the lecturer can open the exam and see a ranked list of suspicious pairs, each with a similarity score and a description of the pattern detected
5. The lecturer reviews each flagged pair and marks it as reviewed, suspected, or cleared

The system never accuses anyone. It only surfaces evidence. Every judgement is made by the lecturer.

---

## Roles

There are three types of accounts:

**Student**
- Can browse courses in their department
- Can enrol in courses
- Can submit work to open exams
- Can view their own submission history

**Lecturer**
- Can create exams for their department's courses
- Can view all submissions for their exams
- Can see similarity reports and review flagged pairs

**Administrator**
- Manages the system: creates departments, courses, and user accounts
- Assigns lecturers to courses
- Enrols students in courses
- Can activate or deactivate accounts

---

## Student: Step by Step

### Finding your courses

After logging in, go to **Courses**. You will see all courses available in your department. Courses you are already enrolled in are marked. Click **Enrol** to join a course.

### Submitting work

Once enrolled in a course, go to the course page and find the exam you want to submit to. The exam page shows:
- Whether the submission window is currently open
- The deadline
- Whether you have already submitted

If the window is open, click **Submit**. You will be asked to upload a file. Accepted formats are shown on the page (typically PDF, DOCX, or TXT). There is also a file size limit — if your file is too large, the system will tell you.

**You can resubmit.** If you upload again before the deadline, your previous submission is replaced. Only your most recent upload is kept.

Once submitted, you will see a confirmation with a timestamp.

### After the deadline

You can view your past submissions under **My Submissions**. If your submission has been analysed, you will see an originality score. This is not a grade — it is a measure of how different your submission is from others in the same exam. A higher originality score means less similarity was detected.

---

## Lecturer: Step by Step

### Creating an exam

From your dashboard, click **New Exam**. Fill in:

- **Course** — which course this exam belongs to
- **Title** — the name of the exam
- **Description** — optional instructions for students
- **Opens at** — when students can start submitting
- **Closes at** — the deadline
- **Allowed file formats** — which file types students may upload (e.g. pdf,docx,txt)
- **Max file size** — the upload limit in megabytes
- **Similarity threshold** — the minimum similarity score for a pair to appear in your report (default 40%)

Times are entered in Lagos time (WAT, UTC+1).

### Viewing submissions and reports

Click on an exam from your dashboard to see:
- All submissions received, with upload times
- The analysis job status (pending, running, completed, or failed)
- A ranked list of flagged pairs above your similarity threshold

### Understanding the similarity report

Each flagged pair shows:

**Similarity score** — a percentage from 0 to 100. Higher means more similar. This is the combined result of two independent measures (vocabulary overlap and exact phrase matching).

**Plagiarism type** — the system's assessment of the pattern:

| Type | What it means |
|---|---|
| **Verbatim** | Large blocks of identical text were found. Classic copy-paste. |
| **Near-copy** | Very similar vocabulary and phrasing throughout, with small edits. Likely light paraphrasing of the same source. |
| **Patchwork** | Many small copied fragments from different parts of another submission, stitched together. |
| **Structural** | Similar organisation and paragraph ordering even where the actual words differ. May indicate shared planning or outline. |

Each type also comes with a **confidence breakdown** — how strongly the evidence points to each of the four patterns. This helps when the pattern is ambiguous.

### Reviewing a pair

Click on any flagged pair to see a side-by-side view of both submissions, with matched segments highlighted. You can then mark the pair as:

- **Reviewed** — you have looked at it and noted it
- **Suspected** — you believe this warrants further investigation or action
- **Cleared** — you have reviewed it and are satisfied there is no misconduct

You can also add notes. These are stored for audit purposes.

---

## Administrator: Step by Step

### Setting up departments and courses

Go to **Departments** and create each department with a name and short code. Then go into each department and create its courses. Each course needs a title, a code, and an assigned lecturer.

### Managing users

Go to **Users** to see all accounts. From here you can:
- Change a user's role
- Assign a user to a department
- Deactivate an account (the user will not be able to log in)
- Reactivate a previously deactivated account

### Enrolling students

Go to a course's detail page and use the **Enrol Student** section to add students. Students can also self-enrol from their own course browser, but only within their department.

---

## Frequently Asked Questions

**Does a high similarity score mean a student cheated?**
No. It means the system found textual overlap between two submissions. Overlap can happen for many legitimate reasons — the same source material, the same lecture notes, or a narrow question that naturally produces similar answers. The lecturer reviews every flagged case and makes the final judgement.

**What if the analysis job fails?**
The system retries automatically up to three times. If it still fails, the job status on the exam page will show as **Failed**. Contact your system administrator.

**Can students see each other's submissions?**
No. Students can only see their own submissions and their own originality score. They cannot see who they were compared against or what the similarity score was.

**What file types are supported?**
PDF, DOCX, and TXT. The lecturer sets which formats are accepted per exam. If you upload an unsupported format, the system will reject it and tell you what is allowed.

**Can I submit after the deadline?**
No. The submission window is enforced automatically. Once the closing time passes, the upload form will not accept new files.

**What does the originality score on my submission mean?**
It is `1 minus the highest similarity score` found between your submission and any other submission in the same exam. A score of 1.0 means no significant similarity was detected. A score of 0.3 means the most similar pair involving your submission had a 70% similarity score. It is not a grade and does not directly indicate academic misconduct.