# Recruitment Management

Group 1 describes how HR publishes jobs, reviews submitted applications, invites
or rejects candidates, and reports on outcomes. An authenticated employee needs
the HR role for these flows (NFR05). Interviewers use assignment-scoped access
in Group 3. See the [business index](README.md) for source filenames and
[implementation notes](implementation-notes.md) for repository coverage.

## Job Postings and Criteria

| State | Availability and next action |
| --- | --- |
| `DRAFT` · Nháp | Internal. HR can edit it, set its criteria, and publish it once valid. |
| `OPEN` · Đang mở | Publicly visible, eligible for recommendations and new applications. HR may update or close it. |
| `CLOSED` · Đã đóng | Reached by HR action or expiration. Existing applications and scheduled interviews continue. Future recruitment for the position requires a new posting. |

### UC1.01 View job postings

HR sees the title, department, headcount, deadline, state, and application count.
Default order is newest creation first, 20 postings per page. Search by keyword
and filter by state, department, or due-date range. Selecting a job shows its
details, current criteria, and available actions. Empty inventory, empty filter
results, and load failures have separate feedback. Reads leave the job unchanged.
Sources UC1.01, BR01.

### UC1.02 Create a job posting

HR enters the position title, department, description, requirements, benefits,
headcount, work mode and location, and application deadline. Publishing includes
[scoring criteria setup](#uc105-configure-scoring-criteria). Publish an Open job
with creator and timestamp after validating required fields, positive headcount,
a deadline on or after the current date, and a valid criteria set. Saving a new
draft validates the title only. A matching open title in the same department
prompts HR to confirm or edit. Cancelling discards input after confirmation.
Validation or persistence errors keep HR in the form. Sources UC1.02, BR01–BR04.

### UC1.03 Update a job posting

HR loads and edits a Draft or Open posting. The detailed save flow references
UC1.02 validation. Publishing a draft explicitly checks all opening conditions.
Saving records changed values, author, and time. Criteria edits go through
UC1.05. If another user saves first, show the conflict and reload current data.
A closed job is read-only. Sources UC1.03, BR02–BR05, NFR10. See
[draft validation](implementation-notes.md#job-and-report-contracts) for the
draft edit boundary.

### UC1.04 Close a job posting

HR starts with an Open job. Before confirmation, show the number of applications
waiting for HR and the number of interviews yet to occur. On confirmation, record
the closure and remove the job from the public listing, suggestions, and
submission paths. The system also closes jobs past the application deadline.
Existing applications continue through review and existing interviews continue
as scheduled. Cancel or failed save leaves the current state in place. If the job
already closed, notify HR and refresh the details. Sources UC1.04, BR01, BR03.

### UC1.05 Configure scoring criteria

HR opens criteria on a Draft or Open job or during creation. The first set starts
with the system default invitation threshold. Each criterion has a name,
description, mandatory or preferred type, and weight. Validate at least one
criterion, positive weights adding to exactly 100%, an invitation threshold
within 0–100, and at least one assigned interviewer. Report sequence S1 checks
that chosen interviewers are active and have the interviewer role.

During job creation, keep the validated set with the form until publication.
For an existing job, save a new version and make it current for later
applications. When there are already scored applications, warn that the scores
and version of those applications are preserved and obtain confirmation.
Highlight invalid weights, limits, or missing selections. Closed job criteria
are read-only. See [criteria versioning](implementation-notes.md#criteria-versioning).
Sources UC1.05, BR04–BR05, report §4.2.1.

## HR Review and Decisions

### UC1.06 View submitted applications

HR can find all submitted applications, including automatically invited ones.
Show candidate name, position, submission date, AI score if available, and state.
Default to newest submission first, 20 records per page. Filter by position,
state, score, or submission date and search by name, email, or phone. HR can sort
by score or state. A review notification opens the pending-review filter.
Selecting a record shows contact details, position, score, and state history and
logs access. Distinguish empty results from a record whose CV file cannot be
opened. In the latter case, extracted data remains visible if available.
Sources UC1.06, BR07, NFR06.

### UC1.07 Review an application

The queue contains applications in *Chờ HR duyệt*. Show oldest first, with AI
score, age, and notice of approaching or missed deadlines. The default review
deadline is five working days from entry into the queue, and overdue items trigger
a reminder (BR25). See UC1.08 before recording a decision. HR may defer, invite
via UC1.09, or reject via UC1.10. The review records the actor, decision, and
time. A completed decision leaves the queue.

A closed posting adds a warning and remains reviewable. An application that
qualified for automatic invitation but could not be scheduled displays its
fallback note and failure reason. If another HR user already decided, refresh
the queue instead of overwriting the result. Branch 5d keeps an incomplete
invitation in review. Confirm the [delivery boundary](implementation-notes.md#invitation-delivery)
before defining this behavior for successful bookings with failed email.
Sources UC1.07, BR06–BR08, BR25, NFR10.

### UC1.08 View application and score details

Show contact and job information, submission date, original CV if available,
and extracted experience, skills, and education. Read the stored total, threshold,
criteria version, and per-criterion score, weight, and explanation. The group
spec also displays CV excerpts as evidence. Highlight missed mandatory
criteria. If AI could not score the CV, show the reason for manual assessment.
If the original file fails, continue to show extracted data where available.
Viewing or downloading a CV requires authorization and audit trail. This read
uses saved data and makes no new AI request. See
[AI evidence](implementation-notes.md#ai-scoring-and-evidence).
Sources UC1.08, NFR06–NFR09, NFR16.

### UC1.09 Invite to an interview

Starts when HR chooses to advance a pending application. Query assigned
interviewers for availability over the next seven working days and show up to
five valid slots. HR selects a slot and one interviewer. HR may try a different
interviewer or enter another time when suggestions are unavailable, with the same
calendar checks. HR previews the email and may edit the note. Time and the
required Meet and response links come from the scheduling flow.

On confirmation, book the Calendar event with Meet, issue the candidate reply
link, send the invitation with its deadline, and move the application to
*Đã mời phỏng vấn* on the successful path. Cancel before booking leaves the
application pending. For Google failures, retry once and retain pending review
if booking cannot complete. Fetch fresh availability if the slot was taken.
For exhausted email retries after a booking, the UC retains the event, flags the
delivery failure, and alerts HR. An invalid address also prompts HR follow-up.
Use the [shared scheduling and delivery rules](candidate-application.md#interview-scheduling-and-delivery).
Sources UC1.09, BR09, BR11, BR20, BR23, NFR03.

### UC1.10 Reject an application

HR chooses an internal reason and confirms rejection. The Other reason
requires a description. Record *Đã từ chối*, the reason, decision maker, and
time. Send a thank-you email that omits internal reasons and AI scores. Include
a [retention consent link](candidate-application.md#uc213-consent-to-retain-a-cv)
unless the candidate already consented. In that case, confirm the retention in
the email. Cancelling leaves the application in its previous state. Failed
email follows BR11 and flags the record while the rejection stands. An invalid
email is flagged for HR. Sources UC1.10, BR08, BR10–BR11, BR21, NFR03.

## Reporting

### UC1.11 View reports

HR selects one of the three report types below, a date range, and position
or department filters. Default to the most recent 30 days and accept at most
12 months. Reject reversed or overly long ranges. Display a chart and aggregate
table or an empty state for the selected range. Filters can be changed without
mutating business records. Only aggregate data may appear. Sources UC1.11,
BR12–BR13.

### UC1.12 View the recruitment funnel

Count CV submissions, OTP-verified applications, interview invitations (automatic
or manual), completed interviews, interview passes, probation acceptances, and
probation passes. Include candidate declines and non-responses at relevant
stages, stage-to-stage conversion rates, and average time from application to
invitation. A stage can be broken down by position. Later stages require
Group 3 and Group 4 events. See [report definitions](implementation-notes.md#job-and-report-contracts)
for cohort and denominator questions. Sources UC1.12, BR12–BR13, BR24.

### UC1.13 View AI screening statistics

Show the score distribution, proportions invited automatically or routed to HR,
and the proportion that AI could not score. Compare the HR pass rate in the
low-score cohort and interview pass rates for automatically invited and
HR-approved applicants. Allow breakdown by job or criteria version. Show a
small-sample warning for a nonempty cohort under ten applications. Sources UC1.13,
BR05–BR06, BR12–BR13.

### UC1.14 View probation statistics

Show counts of ongoing and ended periods, pass/fail rates, task pass rate, and
on-time submission rate by job or department. HR can drill down to the hiring
round for a position. Show the specified empty state if there is no probation
data. The calculations depend on Group 4's period, conclusion, and task data.
Sources UC1.14, BR12–BR13.

### UC1.15 Export a report

HR can export the currently filtered report when it has data. Excel or PDF
contains the report name, period, filters, aggregate table, exporter, and export
time. PDF also includes the chart. Omit candidate personal information and log
the export. A generation failure allows retry. Sources UC1.15, BR12–BR13.

## Quality Targets

The Group 1 specification §4.1 gives the following targets. The report leaves
NFR01 and NFR02 blank in its summary. See
[source differences](implementation-notes.md#job-and-report-contracts).

| Source | Expected property |
| --- | --- |
| NFR01–NFR02 | Job and application lists within 2 seconds with 10,000 applications. A 12-month report within 5 seconds and export within 10 seconds. |
| NFR03–NFR04 | Preserve HR decisions if Google or email fails. Queue business emails and retry under BR11. Group 1 specifies a 10-second external call timeout. |
| NFR05–NFR08 | Enforce HR access on the server, log views and review decisions, encrypt CVs at rest, use HTTPS, and apply the documented privacy and consent constraints. |
| NFR09–NFR10 | Show explainable scores and detect concurrent edits or review decisions. The evidence requirement is open. |
| NFR11–NFR12 | Vietnamese UI, field-level validation, at most three review actions after opening details, and support for the specified Chrome, Edge, and Firefox browsers at widths from 1280 px. |
| NFR13–NFR18 | Apply the [shared safeguards](implementation-notes.md#shared-safeguards). |
