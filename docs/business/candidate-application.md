# Application and Job Recommendations

Group 2 starts with a public visitor. A CV upload creates a temporary
submission. Selecting a still-open job and verifying the candidate email
creates an application. Recommendations can help the candidate choose a job.
Scoring happens after application creation and determines the screening route.
See the [business index](README.md) for sources and states.

## CV Intake and Recommendations

### UC2.01 Submit a CV

The candidate provides name, phone, email, and a CV, accepts the data-processing
notice, and completes CAPTCHA. Server checks include a nonblank name up to
100 characters, valid email, ten phone digits, a readable PDF or DOCX up to
5 MB, and at most ten CV submissions per IP per hour. Validate the actual file
type and scan the file before using it. Correctable input errors return to
the form. CAPTCHA failure refreshes the challenge. Rate limiting prompts the
candidate to retry later. A storage failure preserves form data except the file.

Save the CV and temporary submission, then run UC2.02 and continue to UC2.03.
Partially extracted CVs are flagged for HR. If the AI service fails, the
candidate can still choose among open jobs without recommendations.
Sources UC2.01, BR14–BR15, BR22, BR26, NFR17, NFR23, NFR25.

### UC2.02 Extract CV data

Read the stored CV text and request structured education, employment and
durations, skills, languages, and certifications. Validate the AI response
against a schema. A scan can use OCR in the detailed UC, with partial output
flagged for HR. If no text can be extracted, ask for another CV. If the provider
fails, times out, or returns an invalid structure, the UC calls for a retry.
After failure, keep the submission and mark it unparsed. See the
[CV and AI contract](implementation-notes.md#ai-scoring-and-evidence) for the
OCR and timeout differences. Sources UC2.02, NFR16, NFR19, NFR25.

### UC2.03 Recommend jobs

With a valid submission in the current candidate session, compare extracted
CV data with Open jobs. Display scores and short reasons at or above the
configured recommendation threshold, ordered by descending fit. The default
limit is five results. Each result shows position, department, deadline, fit,
and actions to view details or apply.

On request, or if parsing or recommendations fail, show the Open jobs without
fit scores. If the results are below the threshold or no jobs are open, show
the applicable empty state and offer consent to retain the CV for future jobs.
Ask for a new submission if the temporary one has expired. This step can save
retention consent and leaves application creation to UC2.05.
Sources UC2.03, BR01, BR18, BR21, BR26.

### UC2.04 View a job

Selecting a suggested or browsed job opens the description, requirements,
benefits, location, work mode, deadline, and any available fit information.
The candidate can go back or apply. If the job closes while the candidate is
browsing, explain that it no longer accepts applications and refresh the list.
Sources UC2.04, BR01, BR03.

## Application and Screening

### UC2.05 Apply to a job

With a valid CV submission, the candidate chooses an Open job. Check whether
that email has already applied to the job. Show the job, candidate name and
email, and filename for confirmation. Editing contact information returns to
the submission form. Cancelling or discovering that the job has closed returns
the candidate to the list. When the email has already applied, explain the
duplicate and offer other open jobs.

Include UC2.06. On successful verification, create the application linking
the CV and job, with state *Đang chấm điểm*. Show the acknowledgment and queue
UC2.08 so the candidate can leave without waiting. The source acknowledgment
promises a result by email within five working days. See
[review timing](implementation-notes.md#invitation-delivery). Job availability
and email/job uniqueness must hold when the application is created, including
requests that race with one another or with closure. If the save fails after
verification, the UC requires a new OTP. The submitted CV leaves the temporary
cleanup path. Sources UC2.05, BR01, BR17, BR19, BR25–BR26, NFR21.

### UC2.06 Verify an OTP

Generate a six-digit code for the requesting purpose, store its hash, and
send the code by email. UC2.05 uses application verification and UC5.18 uses
password reset in the source model. The default lifetime is five minutes.
Show time remaining and make resend available after 60 seconds. Check the
code, purpose, and expiration on the server. Success consumes the code and
resumes the requesting use case. Expired codes require a new one. Wrong-purpose
codes are treated as wrong codes. The detailed candidate flow displays the
remaining attempts for a wrong code. The source describes a five-attempt limit
and 15-minute lockout. Confirm the
[attempt boundary and recovery rules](implementation-notes.md#otp-and-passwords).

An initial send failure gets one immediate retry. Continued failure permits
a later attempt. UC2.06 calls out invalid address feedback for the candidate
flow. Internal recovery also has the generic-response requirement in BR42.
Sources UC2.06, BR16, BR42, NFR20, NFR22.

### UC2.07 Resend an OTP

Check the 60-second cooldown and default limit of three resends per hour.
If allowed, invalidate the previous code, generate and send a new one, and
reset the countdown. Block early or over-quota requests. Handle delivery
failures using the UC2.06 send error path. Sources UC2.07, BR16.

### UC2.08 Score a CV

Run in the background for an application already created after successful OTP.
Use the criteria version applicable at submission under BR05 and report §3.1.2.
Request per-criterion scores in 0–100 and explanations. UC2.08 also specifies
evidence excerpts, schema validation, and verification against the CV. Compute
the weighted total in application logic and save the total, component scores,
explanations, and criterion version. The report snapshots criterion weights to
make the result reproducible. See [AI evidence](implementation-notes.md#ai-scoring-and-evidence)
and [criteria versioning](implementation-notes.md#criteria-versioning).

| Outcome | Next action |
| --- | --- |
| Total reaches the job threshold and every mandatory criterion is met | Continue to UC2.09. |
| Total is below the threshold or a mandatory criterion is missed | Move to *Chờ HR duyệt*, notify HR, and start its review deadline. |
| Extraction failed, or scoring remains unavailable after the specified retries with increasing delays | Move to HR review with the reason that no AI score is available. |
| Invalid schema or an unverifiable excerpt under the detailed UC | Discard the unreliable criterion result, flag it, and send to HR review even if the remaining score is high. |

Only HR can reject an application. Sources UC2.08, BR05–BR08, BR19, BR25,
NFR16, NFR21, report S2.

### UC2.09 Automatically invite to an interview

For an eligible score, check assigned interviewers' availability over seven
working days and select the earliest valid slot and its interviewer. Create
the Google Calendar event and Meet link. Issue the candidate reply link, send the
invitation, and move the application to *Đã mời phỏng vấn* on the successful
path. Notify HR. With no eligible slot, persistent Google failure after one
retry, or a slot conflict after up to two renewed searches, move to
*Chờ HR duyệt* with the note that the candidate qualified and needs a manual
invitation. Report S3 shows cancellation of a Google event created before a
local booking conflict. A failed email after booking follows the rule below.
Sources UC2.09, BR06, BR09, BR11, BR20, BR23, NFR21, report §4.2.3.

## Interview Scheduling and Delivery

Both [manual](recruitment-management.md#uc109-invite-to-an-interview) and
automatic invitations use BR09. The slot must be within configured working
hours, after the reply deadline by at least one working day by default, and
free on the assigned interviewer's calendar. Report §5.2.6 and NFR35 give
additional constraints of one active interview per application and no
overlapping interviews for an interviewer, including concurrent bookings.

The invitation includes the job, time, Meet link, reply link, explicit
deadline, and the consequence of no response. Group 3 receives successful
bookings and owns interview confirmation, rescheduling, and results. See
[the rescheduling boundary](implementation-notes.md#interview-response-boundary)
for the two source variants.

BR11 calls for up to three email retries five minutes apart and a flag and HR
notice after exhaustion. The invitation use cases retain an existing event
when email retries fail. An invalid candidate address is flagged for follow-up
by phone. Keep booking, queued email, provider acceptance, and receipt
distinguishable when specifying [delivery behavior](implementation-notes.md#invitation-delivery).
OTP delivery has its own retry path in UC2.06.

## Candidate Responses and Retention

### UC2.10 Handle a reply link

A candidate opens a link scoped to the related record and purpose. Check that
the link exists, is still valid, and has not been used. Display the related
content and reply deadline. Opening the page leaves the link usable.
Recording the confirmed response and its timestamp consumes the link. If
saving fails, the candidate can try again with the same unconsumed link.
An invalid link shows an error. An expired link shows the deadline outcome and
HR contact. A used link displays the response already recorded.

BR20 and NFR22 specify single use and at least 128 bits of randomness. Under
BR23, the default deadline is the end of the second working day **after** the
email send date, skipping weekends and company holidays. For example, a
Friday send expires Tuesday at closing time when Monday and Tuesday are
working days. An unanswered link expires even if the candidate never opens it.

| Expired reply | Effect under BR24 |
| --- | --- |
| Interview invitation | Move to *Từ chối phỏng vấn* and cancel the calendar event. |
| Probation offer | Move to *Từ chối thử việc*. |
| Retention question | Record no consent to retain the CV for later recruitment. |

Invalidate the expired link, record the non-response reason, notify HR, and
email the candidate. NFR33 calls for expiration processing at least every
15 minutes and the corresponding transition within 15 minutes of expiry.
Sources UC2.10, BR20, BR23–BR24, NFR22, NFR33.

### UC2.11 Respond to a probation offer

The application passed the interview and has a valid probation offer from
Group 3. Show the role, start date, location, duration, manager, and reply
deadline. Acceptance records the response and triggers UC2.12. The successful
path shows *Đang thử việc*, gives account guidance, and notifies HR and the
manager. A provisioning failure needing manual action moves the application
to *Chờ cấp tài khoản*. Notify Admin and tell the candidate that the account
details will follow. Check the [partial success boundary](implementation-notes.md#probation-handoffs).

For a decline, accept an optional reason up to 500 characters, record
*Từ chối thử việc*, and notify HR. An unanswered expiry follows BR24.
Sources UC2.11, BR20, BR23–BR24, and Group 3 UC3.09.

### UC2.12 Provision a probation account

After offer acceptance, choose a unique company mailbox name based on the
candidate's given and family names. The source adds a numeric suffix for
collisions, including addresses previously used by locked or deleted accounts.
Provision the Google Workspace mailbox with first-login password change,
create the internal account with the standalone probation role and offer
context, and send onboarding instructions to the personal email. The source
flows through UC5.18 for first-time system password setup using the company
mailbox. Record provisioning history.

On Google failure, license exhaustion, or timeout, the UC calls for up to
three queued retries, followed by Admin action through UC5.02. If the mailbox
exists but internal account creation still fails after one retry, preserve
the mailbox for manual recovery. Exhausted notification retries alert Admin
and HR for follow-up. The source retains the account when the error is confined
to delivery. See the [implementation baseline](implementation-notes.md#repository-baseline)
for the existing invitation flow. Sources UC2.12, BR11, BR30, BR39,
NFR22, NFR29.

### UC2.13 Consent to retain a CV

A thank-you email from HR rejection or an unsuccessful interview can ask
the candidate to keep the CV for later openings. The reply page shows the
data, purpose, default 12-month period, and right to withdraw. On consent,
record the time, version of the consent notice, and expiry. If consent already
exists, show the current expiry. A visit without consent leaves the CV
ineligible for later recruitment. UC2.03 also offers an explicit opt-in
directly when there are no suitable recommendations.

For an unsubmitted CV without retention consent the default cleanup deadline
is 24 hours. Retained CVs are subject to expiration or withdrawal. The detailed
sources and report use both deletion and anonymization. Confirm
[what is retained or removed](implementation-notes.md#retention) before
designing jobs that remove data. Sources UC2.13, BR10, BR20–BR21, BR24, BR26,
NFR23.

## Quality Targets

| Source | Expected property |
| --- | --- |
| NFR13–NFR18 | Apply the [shared safeguards](implementation-notes.md#shared-safeguards). |
| NFR19–NFR20 | Recommendations within 15 seconds of sending the CV, OTP arrival within 30 seconds, and an eligible automatic invitation within ten minutes of application. |
| NFR21–NFR22 | Queue scoring and automatic invitation and preserve submitted applications through provider errors. Protect OTPs, response links, and first login. |
| NFR23–NFR25 | Enforce consent and retention rules, support the candidate flow at widths from 360 px, keep the intake form to at most five input fields, and gate and bound AI requests. |
| NFR33 | Process expired replies on the documented interval and within the deadline described in UC2.10. |
