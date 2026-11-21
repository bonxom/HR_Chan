# System Administration

Group 5 covers internal accounts, authorization, work reassignment, audit,
settings, and passwords. The flows below describe the Group 5 specification.
See the [repository baseline](implementation-notes.md#repository-baseline) for
the administration and password paths currently implemented.

## Account and Role Rules

- Admin and employee are separate account types. Admin accounts carry no
  business roles and cannot read candidate CVs, scores, or interview results.
  A person who needs both types uses distinct company emails (BR27–BR29).
- Admin assigns roles. Employees have at least one role and can combine HR,
  interviewer, and department manager. Probation is a standalone role tied
  to UC2.12 or the manual fallback for *Chờ cấp tài khoản* (BR28, BR30).
- Company email addresses must be unique and match the configured company
  domain. Internal accounts are provisioned through authorized flows (BR39).
- Administrative reasons are required for lock, unlock, deletion, role
  removal, Admin creation, and Admin reset. Keep an immutable change record
  with operation, target, actor, timestamp, reason, applicable before/after
  role or value changes, and reassigned work (BR38).
- BR31 protects Admins from self-lock, self-deletion, and self-reset and requires
  at least two active Admins after an Admin lock or deletion. A sole Admin
  triggers a persistent warning. BR32 protects the last active HR. See
  [account safeguards](implementation-notes.md#account-protection-and-reassignment)
  for the source and implementation differences.

## Account Lifecycle and Work Reassignment

### UC5.01 View accounts

Admin lists and searches accounts by name or email, or filters by account
type, roles, department, and status. The source shows 20 per page with name,
email, role, type, department, status, and last login. Selection shows details,
change history, and available operations. Self-targeted lock, delete, and
Admin reset are unavailable. Empty results and load failures get distinct
feedback. Sources UC5.01, BR27–BR31.

### UC5.02 Create an employee account

Admin enters name, company email, and department, and assigns roles via
UC5.08. Validate required fields, company domain, and uniqueness. The source
creates an employee account in *Hoạt động* without a system password, records
the creation, and emails instructions for first-time setup through UC5.18.
The current account starts in `PENDING_SETUP`. See
[OTP and passwords](implementation-notes.md#otp-and-passwords).

For *Chờ cấp tài khoản* after UC2.12, Admin selects the pending case and enters
the manually provisioned company mailbox. The source pre-fills the name and
probation role. Reject manual probation assignment outside this path.
If notifying the employee fails, keep the account and flag delivery after
BR11 retries. Sources UC5.02, BR11, BR27–BR30, BR38–BR41.

### UC5.03 Create an Admin account

Admin enters name, separate company email, and reason. Validate the inputs
and email uniqueness, create an Admin with zero business roles, and record
the action. Send first-time setup instructions, and notify the other Admins.
BR43 gives a newly created Admin a 72-hour setup eligibility window. Use the
same delivery failure handling as UC5.02. Sources UC5.03, BR29, BR38–BR39, BR43.

### UC5.04 Update account details

Admin can edit name, company email, and department on an account that has not
been deleted. Validate domain and uniqueness when saving and record before and
after values. A concurrent save prompts a reload. A manager with active
probation work requires a reassignment warning before a department change.
An email change ends existing sessions and sends the user through recovery
using the new address. Sources UC5.04, BR33, BR36, BR38–BR39.

### UC5.05 Lock or unlock an account

| Action | Prerequisite and effect |
| --- | --- |
| Normal lock | Admin selects another account, checks administrator and HR safeguards, and provides a reason. If there is unfinished work, complete UC5.09 first. Block the normal lock if eligible replacements are unavailable. Record the lock, revoke sessions, and notify the affected user, replacement, and HR as applicable. |
| Emergency lock | For a security reason, lock and revoke sessions immediately. Move unfinished work to *Chờ chuyển giao*. Alert HR and Admin for affected interviews within 24 hours. The last-HR exception is an [open decision](implementation-notes.md#account-protection-and-reassignment). |
| Unlock | Admin provides a reason. The target must be locked and eligible, including the source restriction on probation employees with a recorded conclusion. Invalidate the old password and guide the user through UC5.18. Existing work reassignments stay in effect. |

The source warns Admin to notify the manager when locking a person currently on
probation. Failed lock notification follows BR11 and leaves the account locked.
Sources UC5.05, BR31–BR38, BR44.

### UC5.06 Delete an account by anonymizing it

Admin selects another, locked account with no work pending reassignment.
Check the Admin floor and require a reason, an explicit confirmation, and
re-entry of the target email. On confirmation, remove personal name, email,
password, and department details, display an anonymized name, and keep the
account identifier and operation history. The source transition to *Đã xóa*
is permanent. Block if the email confirmation fails or work remains pending.
See [account deletion](implementation-notes.md#account-protection-and-reassignment)
for current disable behavior. Sources UC5.06, BR31, BR37–BR38.

### UC5.07 Open an Admin password reset window

An Admin selects another active Admin account, gives a reason, and confirms.
Invalidate the target's current password, end its sessions, open the
source's 30-minute reset window, and record the action. Notify both Admins.
The target completes UC5.18. When the window expires without a new password,
the old credential remains invalid and another reset window is needed.
Failed email follows BR11 and prompts direct follow-up.
Sources UC5.07, BR31, BR36, BR38, BR43.

### UC5.08 Assign or remove roles

Admin edits the role set of an employee or assigns initial roles in UC5.02.
Validate the combination and any restriction on probation. Removing a role
requires a reason and an unfinished-work check. If the removed role owns work,
complete UC5.09 before saving. Block removal of the last active HR role
and removals that leave work without an eligible successor. Save and audit
old and new roles and notify the user. New permissions take effect on their
next action. During account creation, keep the selections with the form
until the account is saved.

After Group 4 records a passing probation conclusion, the account goes to
*Chờ Admin xử lý*. Admin can replace the probation role with applicable
employee roles or lock it for completed probation. After a failing
conclusion, the source calls for a lock after the period end date.
Sources UC5.08, BR27–BR30, BR32–BR33, BR38, BR44.

### UC5.09 Reassign unfinished work

A normal lock or removal of a role with unfinished work opens the handover
flow. A department change can require it under UC5.04. Admin or HR can also
open the pending queue after emergency lock. HR's authority here is to assign
pending work. Account or role changes require Admin.

| Work to transfer | Eligible recipient |
| --- | --- |
| Interviewer assignment to jobs, upcoming interviews, or interviews without results | Active account with the interviewer role. |
| A manager's active probation periods, ungraded tasks, or missing conclusions | Active manager in the same department. |

Show work grouped by role or resource. Admin sees a summary with names and
counts. HR can see the relevant recruiting details when working the pending
queue. Confirm a recipient per group and recheck their eligibility at save.
If no recipient is eligible, block normal lock or role removal. If a chosen
recipient became ineligible, refresh the options. Persist reassignment and
record it in the change history. For scheduled interviews, update the active
Calendar event's participants and notify the replacement. If Google fails,
retain the local reassignment, flag the calendar for manual synchronization,
and notify HR. Email errors follow BR11. Sources UC5.09, BR32–BR35, BR38.

## Audit and Configuration

### UC5.10 View activity logs

Admin sees newest events first, with actor, target, action, timestamp, and
reason. Filter by action, actor, and date range up to 12 months. Open a
record to see administrative before/after values or reassignment history.
The audit is append-only. Apply the Admin data boundary to records about
business operations. Sources UC5.10, BR29, BR38, NFR26, NFR30.

### UC5.11 Export activity logs

With matching records in the current filter, Admin can export Excel or PDF.
Include the filter result, exporter, and export time and log the export.
Require a narrower filter above 50,000 records. Show a retry path if
generation fails. Sources UC5.11, BR38, NFR30.

### UC5.12 Configure the system

The common flow for UC5.13–UC5.16 displays the current value, default, and
allowed range. Admin edits, restores a default, or cancels. Validate before
save and record the previous value, new value, actor, and time. A concurrent
update requires reload. The change applies to actions after saving, with a
one-minute propagation target across servers. Sources UC5.12, BR45–BR47, NFR31.

### UC5.13 Configure working hours

Admin edits work hours by weekday, holidays, interview duration, and the
minimum gap between response deadline and interview. The default gap is one
working day. Validate time ordering and duration of 15–180 minutes. If a newly
added holiday affects existing interviews, show the affected bookings and let
HR handle them through the interview flow. Saving the holiday leaves those
bookings in place. Sources UC5.13, BR09, BR23, BR45, BR47.

### UC5.14 Manage email templates

Admin edits subjects and bodies for OTP, interview, offer, consent, account,
password, and deadline messages. Show allowable and required variables and
preview with sample data. Reject unknown variables or missing required ones.
Escape inserted values in content and remove line breaks from headers. Admin
may send a sample to their own mailbox. Test delivery failure does not prevent
saving an otherwise valid template. Sources UC5.14, BR46, NFR15, NFR18.

### UC5.15 Configure deadlines

Admin manages OTP lifetime, candidate reply days, Admin reset window, temporary
submission expiry, retention duration, HR review due time, and session idle
expiry. Validate the documented bounds. Issued OTPs and response links keep
their original expiration. Sources UC5.15, BR16, BR21, BR23, BR25–BR26,
BR43, BR45, BR47, NFR27.

### UC5.16 Configure AI thresholds

Admin sets the default automatic invitation threshold, the recommendation
threshold, and the maximum count of suggested jobs. Thresholds use a 0–100
scale. The result count is configurable from 1–10, with a default of five.
The default invitation threshold applies to new jobs. Existing criteria sets
keep their configured threshold. Sources UC5.16, BR04–BR05, BR18, BR45, BR47.

| Setting | Source default | Bounds stated in the group spec |
| --- | --- | --- |
| Interview duration | Uses configuration | 15–180 minutes (UC5.13) |
| Gap after candidate reply deadline | 1 working day (BR09) | UC5.13 gives no numeric range |
| OTP lifetime | 5 minutes (BR16) | 1–15 minutes (UC5.15) |
| Candidate reply deadline | End of 2nd working day after send (BR23) | 1–5 working days (UC5.15) |
| Admin reset window | 30 minutes (BR43) | UC5.15 gives no numeric range |
| Unsubmitted CV expiry | 24 hours (BR26) | UC5.15 gives no numeric range |
| CV retention after consent | 12 months (BR21) | Up to 24 months (UC5.15) |
| HR review deadline | 5 working days after entry into review (BR25, UC2.08) | UC5.15 gives no numeric range |
| Session idle expiry | 30 minutes (NFR27) | UC5.15 gives no numeric range |
| Automatic invitation and recommendation thresholds | Values from system configuration (BR04, BR18) | 0–100 (UC5.16) |
| Suggestion count | 5 (BR18) | 1–10 (UC5.16) |

## Passwords

### UC5.17 Change a password

An authenticated internal user enters their current password, a new password,
and confirmation. Verify the current credential. BR40 requires at least eight
characters with letters and digits and a different password. On success, store
a hash, end other sessions, and notify the user by email. The source describes
blocking the change operation for 15 minutes after five incorrect current
password attempts and sending a warning. A notification failure leaves the
password changed and follows BR11. Sources UC5.17, BR36, BR40–BR41, NFR27–NFR28.

### UC5.18 Recover or set a password for the first time

From the login page, submit the company email. Check recovery request limits
of five per hour per email and 20 per hour per IP in BR42. Show the generic
response for eligible and ineligible addresses. The detailed UC shows a
separate retry-later screen when limited. For an eligible account, verify an
OTP through UC2.06 with the password reset purpose before accepting a new
password and confirmation. Save the hash, end all old sessions, log the
operation, send the change notice, and return to login.

Suppress OTP for absent, deleted, or locked accounts. The source allows a
mailbox-only notice for a locked account. Admin eligibility is limited to
the first 72 hours after creation or a UC5.07 reset window, default 30 minutes.
Expired, mismatched, or otherwise invalid proof leaves the password untouched.
Sources UC5.18, BR36, BR40–BR43, NFR27–NFR28. See
[OTP and passwords](implementation-notes.md#otp-and-passwords) for the
implemented email link flow.

## Quality Targets

| Source | Expected property |
| --- | --- |
| NFR13–NFR18, NFR26 | Apply [shared safeguards](implementation-notes.md#shared-safeguards) and server-side role checks, including the Admin business data boundary. |
| NFR27–NFR28 | Hash with bcrypt or Argon2. Default idle timeout is 30 minutes. Login has a five-failure, 15-minute lockout. Confirm the all-sessions wording for password change against UC5.17. The source targets revocation within one minute. |
| NFR29 | Admin mailboxes have Google Workspace two-factor authentication. The mailbox provisioning identity has user creation permission only. |
| NFR30–NFR32 | Audit administration and profile reads in an append-only log. Propagate settings within one minute. Provide an audited server recovery procedure for loss of all Admin access. |
