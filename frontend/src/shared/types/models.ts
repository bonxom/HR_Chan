// Application States matching Section 5.4 of PRJ3 Report
export type ApplicationStatus =
  | 'SCORING'
  | 'PENDING_HR_REVIEW'
  | 'INTERVIEW_INVITED'
  | 'INTERVIEW_CONFIRMED'
  | 'INTERVIEW_DECLINED'
  | 'AWAITING_INTERVIEW_RESULT'
  | 'INTERVIEW_PASSED'
  | 'INTERVIEW_FAILED'
  | 'REJECTED'
  | 'AWAITING_ACCOUNT'
  | 'ON_PROBATION'
  | 'PROBATION_DECLINED'
  | 'PROBATION_PASSED'
  | 'PROBATION_FAILED';

export type JobStatus = 'DRAFT' | 'OPEN' | 'CLOSED';

export type UserRole = 'HR' | 'INTERVIEWER' | 'DEPT_MANAGER' | 'PROBATION' | 'ADMIN';
export type AccountType = 'EMPLOYEE' | 'ADMIN';
export type UserStatus = 'ACTIVE' | 'LOCKED' | 'PENDING_ADMIN' | 'DELETED';

export type InterviewStatus = 'SCHEDULED' | 'CONFIRMED' | 'RESCHEDULE_REQUESTED' | 'CANCELLED' | 'COMPLETED';
export type InterviewResult = 'PASSED' | 'FAILED' | 'ABSENT';

export type ProbationStatus = 'ONGOING' | 'PASSED' | 'FAILED';
export type TaskResult = 'PASSED' | 'FAILED';

export interface User {
  id: number;
  fullName: string;
  email: string; // company email
  accountType: AccountType;
  roles: UserRole[];
  department: string;
  status: UserStatus;
  lastLoginAt?: string;
}

export interface Criterion {
  id: number;
  name: string;
  description: string;
  isMandatory: boolean;
  weight: number; // percentage 0-100, sum must be 100
}

export interface CriteriaSet {
  id: number;
  jobId: number;
  versionNo: number;
  autoInviteThreshold: number; // 0-100
  criteria: Criterion[];
  interviewerIds: number[];
  createdAt: string;
}

export interface JobPosting {
  id: number;
  title: string;
  department: string;
  description: string;
  requirements: string;
  benefits?: string;
  location: string;
  salaryRange?: string;
  employmentType: 'Full-time' | 'Part-time' | 'Contract' | 'Internship';
  headcount: number;
  deadline: string;
  status: JobStatus;
  autoInviteThreshold: number;
  currentCriteriaSetId?: number;
  createdAt: string;
}

export interface Candidate {
  id: number;
  fullName: string;
  email: string;
  phone: string;
  consentAt: string;
  anonymizedAt?: string;
}

export interface CvSubmission {
  id: number;
  candidateId: number;
  fileName: string;
  fileSize: number; // bytes
  fileUrl: string;
  parsedData: {
    fullName?: string;
    email?: string;
    phone?: string;
    education: string[];
    skills: string[];
    experience: { role: string; company: string; duration: string; details: string }[];
    certificates?: string[];
  };
  suggestions: {
    jobId: number;
    matchScore: number;
    reason: string;
  }[];
  expiresAt: string;
  createdAt: string;
}

export interface ApplicationScore {
  criterionId: number;
  criterionName: string;
  weight: number;
  score: number; // 0-100
  aiComment: string;
  evidenceQuote: string;
  meetsMandatory: boolean;
}

export interface Application {
  id: number;
  jobId: number;
  candidateId: number;
  submissionId: number;
  status: ApplicationStatus;
  submittedAt: string;
  aiTotalScore?: number;
  reviewDueAt?: string; // 5 working days from submission
  hrNote?: string;
  rejectReason?: string;
  scores: ApplicationScore[];
}

export interface Interview {
  id: number;
  applicationId: number;
  interviewerId: number;
  startAt: string;
  endAt: string;
  status: InterviewStatus;
  meetLink: string;
  googleEventId?: string;
  autoScheduled: boolean;
  rescheduleNote?: string;
  declineReason?: string;
  result?: InterviewResult;
  evaluations?: {
    criterionId: number;
    rating: number; // 1-5
    note: string;
  }[];
  finalNote?: string;
}

export interface ProbationOffer {
  id: number;
  applicationId: number;
  startDate: string;
  durationDays: number; // 1-180 days
  location: string;
  managerId: number;
  status: 'PENDING' | 'ACCEPTED' | 'DECLINED';
  declineReason?: string;
  responseDeadline: string; // 2 working days
}

export interface ProbationTask {
  id: number;
  probationId: number;
  title: string;
  description: string;
  attachments?: { name: string; url: string; size: string }[];
  dueAt: string;
  createdAt: string;
  submission?: {
    submittedAt: string;
    content: string; // link or file name
    isLate: boolean;
  };
  result?: TaskResult;
  feedback?: string;
  gradedAt?: string;
}

export interface Probation {
  id: number;
  applicationId: number;
  traineeId: number; // User with PROBATION role
  managerId: number; // User with DEPT_MANAGER role
  startDate: string;
  endDate: string;
  status: ProbationStatus;
  conclusionNote?: string;
  concludedAt?: string;
}

export interface AuditLog {
  id: number;
  timestamp: string;
  actorId: number;
  actorName: string;
  actorRole: string;
  actionType: 'ACCOUNT' | 'ROLE' | 'CONFIG' | 'VIEW_APPLICATION' | 'DECISION' | 'HANDOVER';
  target: string;
  reason?: string;
  details: string;
}

export interface SystemSettings {
  workingHours: { start: string; end: string };
  workingDays: number[]; // 1 = Mon ... 5 = Fri
  otpExpiryMinutes: number; // default 5
  candidateResponseDays: number; // default 2
  hrReviewDays: number; // default 5
  retentionMonths: number; // default 12
  defaultAutoInviteThreshold: number; // default 80
  defaultSuggestionThreshold: number; // default 60
  maxSuggestions: number; // default 5
}

