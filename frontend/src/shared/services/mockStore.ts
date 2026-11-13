import {
  User,
  JobPosting,
  CriteriaSet,
  Application,
  Candidate,
  Interview,
  Probation,
  ProbationTask,
  AuditLog,
  SystemSettings,
  UserRole,
  ApplicationStatus,
} from '../types/models';

const INITIAL_USERS: User[] = [
  {
    id: 1,
    fullName: 'Lê Minh HR',
    email: 'minh.le@hrchan.vn',
    accountType: 'EMPLOYEE',
    roles: ['HR'],
    department: 'People & Culture',
    status: 'ACTIVE',
    lastLoginAt: '2026-11-13T08:30:00Z',
  },
  {
    id: 2,
    fullName: 'Trần Văn Lead (Interviewer)',
    email: 'van.tran@hrchan.vn',
    accountType: 'EMPLOYEE',
    roles: ['INTERVIEWER'],
    department: 'Engineering',
    status: 'ACTIVE',
    lastLoginAt: '2026-11-13T09:15:00Z',
  },
  {
    id: 3,
    fullName: 'Nguyễn Thị Hương (Manager)',
    email: 'huong.nguyen@hrchan.vn',
    accountType: 'EMPLOYEE',
    roles: ['DEPT_MANAGER'],
    department: 'Engineering',
    status: 'ACTIVE',
    lastLoginAt: '2026-11-12T17:00:00Z',
  },
  {
    id: 4,
    fullName: 'Phạm Quốc Bảo (Probation Trainee)',
    email: 'bao.pham@hrchan.vn',
    accountType: 'EMPLOYEE',
    roles: ['PROBATION'],
    department: 'Engineering',
    status: 'ACTIVE',
    lastLoginAt: '2026-11-13T08:00:00Z',
  },
  {
    id: 99,
    fullName: 'System Administrator',
    email: 'admin@hrchan.vn',
    accountType: 'ADMIN',
    roles: ['ADMIN'],
    department: 'IT Operations',
    status: 'ACTIVE',
    lastLoginAt: '2026-11-13T07:45:00Z',
  },
];

const INITIAL_JOBS: JobPosting[] = [
  {
    id: 1,
    title: 'Senior Python / FastAPI Backend Engineer',
    department: 'Engineering',
    location: 'Hà Nội (Hybrid)',
    employmentType: 'Full-time',
    salaryRange: '35,000,000 - 55,000,000 VND',
    headcount: 2,
    deadline: '2026-12-15',
    status: 'OPEN',
    autoInviteThreshold: 80,
    currentCriteriaSetId: 1,
    createdAt: '2026-11-01T10:00:00Z',
    description:
      'Chúng tôi tìm kiếm Senior Backend Engineer am hiểu kiến trúc vi dịch vụ, FastAPI, Async SQLAlchemy và tích hợp pgvector để phát triển lõi AI-assisted HR Platform.',
    requirements:
      '- Tối thiểu 4 năm kinh nghiệm làm việc với Python, chuyên sâu FastAPI.\n- Nắm vững thiết kế CSDL PostgreSQL, asyncpg, vector similarity search.\n- Kinh nghiệm triển khai Docker, microservices và CI/CD.\n- Khả năng đọc hiểu tài liệu tiếng Anh kỹ thuật tốt.',
    benefits:
      '- Lương cạnh tranh + thưởng hiệu suất hàng quý.\n- Bảo hiểm sức khỏe PVI cao cấp cho nhân viên và người thân.\n- Cung cấp MacBook Pro M3 Max + màn hình 4K.',
  },
  {
    id: 2,
    title: 'Frontend Lead Engineer (React / TypeScript)',
    department: 'Engineering',
    location: 'Hà Nội / TP.HCM',
    employmentType: 'Full-time',
    salaryRange: '40,000,000 - 60,000,000 VND',
    headcount: 1,
    deadline: '2026-12-20',
    status: 'OPEN',
    autoInviteThreshold: 85,
    currentCriteriaSetId: 2,
    createdAt: '2026-11-05T08:00:00Z',
    description:
      'Xây dựng giao diện ứng dụng doanh nghiệp chuẩn hóa, tối ưu hiệu năng TanStack Query, React 19 và Tailwind CSS với trải nghiệm mượt mà.',
    requirements:
      '- 5+ năm phát triển Frontend với React & TypeScript.\n- Am hiểu chuyên sâu Tailwind CSS, component library design system.\n- Thành thạo kiến trúc state, TanStack Query, Vite build optimization.',
    benefits:
      '- Cơ chế làm việc linh hoạt (2 ngày remote/tuần).\n- Tài trợ ngân sách học tập và chứng chỉ quốc tế 20 triệu/năm.',
  },
  {
    id: 3,
    title: 'AI / Machine Learning Engineer (LLM & Embeddings)',
    department: 'AI Research',
    location: 'Hà Nội',
    employmentType: 'Full-time',
    salaryRange: '45,000,000 - 70,000,000 VND',
    headcount: 1,
    deadline: '2026-12-30',
    status: 'OPEN',
    autoInviteThreshold: 80,
    createdAt: '2026-11-08T09:00:00Z',
    description:
      'Nghiên cứu và triển khai pipeline trích xuất CV, semantic search với pgvector, tích hợp MCP Server cho các tác vụ tự động hóa.',
    requirements:
      '- Kinh nghiệm thực tế với LLM APIs, Prompt Engineering và LangChain/LlamaIndex.\n- Thành thạo kỹ thuật Embedding, vector databases.\n- Có công bố khoa học hoặc đồ án thực tế là điểm cộng lớn.',
    benefits: '- Được cấp quyền truy cập hệ thống GPU A100 chuyên dụng để huấn luyện mô hình.',
  },
];

const INITIAL_CRITERIA_SETS: CriteriaSet[] = [
  {
    id: 1,
    jobId: 1,
    versionNo: 1,
    autoInviteThreshold: 80,
    interviewerIds: [2],
    createdAt: '2026-11-01T10:30:00Z',
    criteria: [
      {
        id: 101,
        name: 'Kinh nghiệm Python & FastAPI',
        description: 'Tối thiểu 3 năm làm việc với Python và FastAPI',
        isMandatory: true,
        weight: 35,
      },
      {
        id: 102,
        name: 'Cơ sở dữ liệu PostgreSQL & Async',
        description: 'Thành thạo async SQLAlchemy, tối ưu query, indexing',
        isMandatory: true,
        weight: 25,
      },
      {
        id: 103,
        name: 'Kinh nghiệm Vector DB & AI Integration',
        description: 'Có kinh nghiệm với pgvector, embedding hoặc LLM',
        isMandatory: false,
        weight: 20,
      },
      {
        id: 104,
        name: 'Tiếng Anh chuyên ngành',
        description: 'Đọc hiểu tài liệu và giao tiếp chuyên môn tốt',
        isMandatory: false,
        weight: 20,
      },
    ],
  },
];

const INITIAL_CANDIDATES: Candidate[] = [
  {
    id: 1,
    fullName: 'Hoàng Văn Nam',
    email: 'nam.hoang@gmail.com',
    phone: '0987654321',
    consentAt: '2026-11-10T14:20:00Z',
  },
  {
    id: 2,
    fullName: 'Đặng Mai Linh',
    email: 'linh.dang@gmail.com',
    phone: '0912345678',
    consentAt: '2026-11-11T09:10:00Z',
  },
  {
    id: 3,
    fullName: 'Nguyễn Thành Đạt',
    email: 'dat.nguyen@gmail.com',
    phone: '0933221100',
    consentAt: '2026-11-12T16:05:00Z',
  },
];

const INITIAL_APPLICATIONS: Application[] = [
  {
    id: 1,
    jobId: 1,
    candidateId: 1,
    submissionId: 1,
    status: 'INTERVIEW_INVITED',
    submittedAt: '2026-11-10T14:25:00Z',
    aiTotalScore: 88,
    scores: [
      {
        criterionId: 101,
        criterionName: 'Kinh nghiệm Python & FastAPI',
        weight: 35,
        score: 95,
        aiComment: 'Ứng viên có 4.5 năm chuyên sâu FastAPI tại công ty công nghệ lớn.',
        evidenceQuote: 'Lead Developer tại TechCorp: thiết kế hệ thống backend FastAPI phục vụ 500k DAU',
        meetsMandatory: true,
      },
      {
        criterionId: 102,
        criterionName: 'Cơ sở dữ liệu PostgreSQL & Async',
        weight: 25,
        score: 85,
        aiComment: 'Nắm vững asyncpg và tối ưu hóa câu truy vấn phức tạp.',
        evidenceQuote: 'Chuyên gia cơ sở dữ liệu PostgreSQL, thiết kế phân vùng bảng và migration Alembic',
        meetsMandatory: true,
      },
      {
        criterionId: 103,
        criterionName: 'Kinh nghiệm Vector DB & AI Integration',
        weight: 20,
        score: 80,
        aiComment: 'Đã từng ứng dụng pgvector cho hệ thống tìm kiếm sản phẩm thông minh.',
        evidenceQuote: 'Xây dựng dịch vụ Recommendation dựa trên pgvector và OpenAI Embeddings',
        meetsMandatory: true,
      },
      {
        criterionId: 104,
        criterionName: 'Tiếng Anh chuyên ngành',
        weight: 20,
        score: 85,
        aiComment: 'IELTS 7.0, tự tin giao tiếp.',
        evidenceQuote: 'IELTS 7.0 (2024), làm việc trực tiếp với khách hàng Singapore',
        meetsMandatory: true,
      },
    ],
  },
  {
    id: 2,
    jobId: 1,
    candidateId: 2,
    submissionId: 2,
    status: 'PENDING_HR_REVIEW',
    submittedAt: '2026-11-11T09:15:00Z',
    aiTotalScore: 74,
    reviewDueAt: '2026-11-18T17:00:00Z',
    hrNote: 'Điểm tổng 74/100, dưới ngưỡng tự động 80 nhưng kinh nghiệm thực tế rất tốt. Cần HR đánh giá.',
    scores: [
      {
        criterionId: 101,
        criterionName: 'Kinh nghiệm Python & FastAPI',
        weight: 35,
        score: 80,
        aiComment: '2.5 năm kinh nghiệm Python, chuyển từ Django sang FastAPI 1 năm gần đây.',
        evidenceQuote: 'Python Developer tại VinHub: bảo trì dịch vụ Django và chuyển đổi sang FastAPI',
        meetsMandatory: true,
      },
      {
        criterionId: 102,
        criterionName: 'Cơ sở dữ liệu PostgreSQL & Async',
        weight: 25,
        score: 75,
        aiComment: 'Hiểu cơ bản ORM nhưng ít kinh nghiệm tuning ở quy mô lớn.',
        evidenceQuote: 'Sử dụng SQLAlchemy và PostgreSQL trong các dự án thương mại',
        meetsMandatory: true,
      },
      {
        criterionId: 103,
        criterionName: 'Kinh nghiệm Vector DB & AI Integration',
        weight: 20,
        score: 60,
        aiComment: 'Chưa có dự án thực tế về Vector DB, mới tham gia khóa học online.',
        evidenceQuote: 'Đã hoàn thành khóa học GenAI & Vector Databases trên Coursera',
        meetsMandatory: true,
      },
      {
        criterionId: 104,
        criterionName: 'Tiếng Anh chuyên ngành',
        weight: 20,
        score: 80,
        aiComment: 'Khả năng đọc hiểu tài liệu lưu loát.',
        evidenceQuote: 'TOEIC 850',
        meetsMandatory: true,
      },
    ],
  },
  {
    id: 3,
    jobId: 1,
    candidateId: 3,
    submissionId: 3,
    status: 'INTERVIEW_PASSED',
    submittedAt: '2026-11-06T11:00:00Z',
    aiTotalScore: 92,
    scores: [],
  },
];

const INITIAL_INTERVIEWS: Interview[] = [
  {
    id: 1,
    applicationId: 1,
    interviewerId: 2,
    startAt: '2026-11-16T14:00:00+07:00',
    endAt: '2026-11-16T15:00:00+07:00',
    status: 'SCHEDULED',
    meetLink: 'https://meet.google.com/abc-hrchan-xyz',
    autoScheduled: true,
  },
];

const INITIAL_PROBATIONS: Probation[] = [
  {
    id: 1,
    applicationId: 3,
    traineeId: 4,
    managerId: 3,
    startDate: '2026-11-01',
    endDate: '2026-12-31',
    status: 'ONGOING',
  },
];

const INITIAL_TASKS: ProbationTask[] = [
  {
    id: 1,
    probationId: 1,
    title: 'Tìm hiểu kiến trúc Modular Monolith và setup môi trường dev',
    description:
      'Đọc tài liệu architecture/overview.md, chạy docker compose db, khởi động backend FastAPI và frontend React thành công. Gửi log kiểm chứng.',
    dueAt: '2026-11-07T17:00:00Z',
    createdAt: '2026-11-01T09:00:00Z',
    submission: {
      submittedAt: '2026-11-06T15:30:00Z',
      content: 'https://github.com/hrchan/onboarding-logs/pull/1',
      isLate: false,
    },
    result: 'PASSED',
    feedback: 'Hoàn thành xuất sắc, hiểu rõ các ranh giới module và nguyên tắc TDD.',
    gradedAt: '2026-11-07T10:00:00Z',
  },
  {
    id: 2,
    probationId: 1,
    title: 'Thiết kế Schema và Migration cho module Candidates',
    description:
      'Tạo migration Alembic định nghĩa bảng candidates và cv_submissions với các trường theo đúng đặc tả tài liệu chương 5.',
    dueAt: '2026-11-20T17:00:00Z',
    createdAt: '2026-11-08T10:00:00Z',
  },
];

const INITIAL_SETTINGS: SystemSettings = {
  workingHours: { start: '08:30', end: '17:30' },
  workingDays: [1, 2, 3, 4, 5],
  otpExpiryMinutes: 5,
  candidateResponseDays: 2,
  hrReviewDays: 5,
  retentionMonths: 12,
  defaultAutoInviteThreshold: 80,
  defaultSuggestionThreshold: 60,
  maxSuggestions: 5,
};

const INITIAL_AUDIT_LOGS: AuditLog[] = [
  {
    id: 1,
    timestamp: '2026-11-13T09:00:00Z',
    actorId: 1,
    actorName: 'Lê Minh HR',
    actorRole: 'HR',
    actionType: 'VIEW_APPLICATION',
    target: 'Application #2 (Đặng Mai Linh)',
    details: 'Xem chi tiết giải trình AI Scoring và CV gốc.',
  },
  {
    id: 2,
    timestamp: '2026-11-10T14:26:00Z',
    actorId: 1,
    actorName: 'System AI Worker',
    actorRole: 'SYSTEM',
    actionType: 'DECISION',
    target: 'Application #1 (Hoàng Văn Nam)',
    details: 'AI chấm đạt 88/100 (vượt ngưỡng 80, đạt đủ tiêu chí bắt buộc) -> Tự động mời phỏng vấn.',
  },
];

class MockStore {
  private users = [...INITIAL_USERS];
  private currentUser: User = INITIAL_USERS[0]; // default to HR
  private jobs = [...INITIAL_JOBS];
  private criteriaSets = [...INITIAL_CRITERIA_SETS];
  private candidates = [...INITIAL_CANDIDATES];
  private applications = [...INITIAL_APPLICATIONS];
  private interviews = [...INITIAL_INTERVIEWS];
  private probations = [...INITIAL_PROBATIONS];
  private tasks = [...INITIAL_TASKS];
  private settings: SystemSettings = { ...INITIAL_SETTINGS };
  private auditLogs = [...INITIAL_AUDIT_LOGS];
  private listeners: (() => void)[] = [];

  subscribe(listener: () => void) {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter((l) => l !== listener);
    };
  }

  private notify() {
    this.listeners.forEach((l) => l());
  }

  // --- User & Role Switching ---
  getCurrentUser() {
    return this.currentUser;
  }

  setCurrentUser(userId: number) {
    const user = this.users.find((u) => u.id === userId);
    if (user) {
      this.currentUser = user;
      this.addAuditLog('ROLE', `Chuyển người dùng sang ${user.fullName} (${user.roles.join(', ')})`);
      this.notify();
    }
  }

  getUsers() {
    return this.users;
  }

  addUser(userData: Omit<User, 'id'>) {
    const newUser: User = {
      ...userData,
      id: Date.now(),
      status: 'ACTIVE',
    };
    this.users.unshift(newUser);
    this.addAuditLog('ACCOUNT', `Tạo tài khoản ${newUser.fullName} (${newUser.email})`);
    this.notify();
    return newUser;
  }

  updateUserStatus(userId: number, status: User['status'], reason: string) {
    const user = this.users.find((u) => u.id === userId);
    if (user) {
      user.status = status;
      this.addAuditLog('ACCOUNT', `Cập nhật trạng thái ${user.fullName} -> ${status}`, reason);
      this.notify();
    }
  }

  updateUserRoles(userId: number, roles: UserRole[], reason: string) {
    const user = this.users.find((u) => u.id === userId);
    if (user) {
      const oldRoles = user.roles.join(', ');
      user.roles = roles;
      this.addAuditLog('ROLE', `Thay đổi quyền ${user.fullName}: [${oldRoles}] -> [${roles.join(', ')}]`, reason);
      this.notify();
    }
  }

  // --- Jobs ---
  getJobs(statusFilter?: JobPosting['status']) {
    if (!statusFilter) return this.jobs;
    return this.jobs.filter((j) => j.status === statusFilter);
  }

  getJobById(id: number) {
    return this.jobs.find((j) => j.id === id);
  }

  createJob(jobData: Omit<JobPosting, 'id' | 'createdAt'>, criteriaData?: Omit<CriteriaSet, 'id' | 'jobId' | 'createdAt' | 'versionNo'>) {
    const newJobId = Date.now();
    const newJob: JobPosting = {
      ...jobData,
      id: newJobId,
      createdAt: new Date().toISOString(),
    };

    if (criteriaData) {
      const criteriaSetId = Date.now() + 1;
      const newCriteriaSet: CriteriaSet = {
        id: criteriaSetId,
        jobId: newJobId,
        versionNo: 1,
        autoInviteThreshold: criteriaData.autoInviteThreshold,
        criteria: criteriaData.criteria,
        interviewerIds: criteriaData.interviewerIds,
        createdAt: new Date().toISOString(),
      };
      this.criteriaSets.push(newCriteriaSet);
      newJob.currentCriteriaSetId = criteriaSetId;
    }

    this.jobs.unshift(newJob);
    this.addAuditLog('DECISION', `Tạo tin tuyển dụng mới: ${newJob.title}`);
    this.notify();
    return newJob;
  }

  updateJobStatus(jobId: number, status: JobPosting['status']) {
    const job = this.jobs.find((j) => j.id === jobId);
    if (job) {
      job.status = status;
      this.addAuditLog('DECISION', `Cập nhật trạng thái tin tuyển dụng #${jobId} -> ${status}`);
      this.notify();
    }
  }

  getCriteriaSetForJob(jobId: number) {
    return this.criteriaSets.find((c) => c.jobId === jobId);
  }

  saveCriteriaSet(jobId: number, criteria: CriteriaSet['criteria'], autoInviteThreshold: number, interviewerIds: number[]) {
    const existing = this.criteriaSets.find((c) => c.jobId === jobId);
    const versionNo = existing ? existing.versionNo + 1 : 1;
    const newSet: CriteriaSet = {
      id: Date.now(),
      jobId,
      versionNo,
      autoInviteThreshold,
      criteria,
      interviewerIds,
      createdAt: new Date().toISOString(),
    };
    this.criteriaSets = this.criteriaSets.filter((c) => c.jobId !== jobId);
    this.criteriaSets.push(newSet);

    const job = this.jobs.find((j) => j.id === jobId);
    if (job) {
      job.currentCriteriaSetId = newSet.id;
      job.autoInviteThreshold = autoInviteThreshold;
    }

    this.addAuditLog('CONFIG', `Cập nhật bộ tiêu chí tin tuyển dụng #${jobId} (v${versionNo})`);
    this.notify();
    return newSet;
  }

  // --- Applications ---
  getApplications() {
    return this.applications.map((app) => {
      const candidate = this.candidates.find((c) => c.id === app.candidateId);
      const job = this.jobs.find((j) => j.id === app.jobId);
      return {
        ...app,
        candidateName: candidate?.fullName || 'N/A',
        candidateEmail: candidate?.email || 'N/A',
        candidatePhone: candidate?.phone || 'N/A',
        jobTitle: job?.title || 'N/A',
        department: job?.department || 'N/A',
      };
    });
  }

  getApplicationById(id: number) {
    const app = this.applications.find((a) => a.id === id);
    if (!app) return null;
    const candidate = this.candidates.find((c) => c.id === app.candidateId);
    const job = this.jobs.find((j) => j.id === app.jobId);
    return {
      ...app,
      candidate,
      job,
    };
  }

  submitApplication(candidateData: { fullName: string; email: string; phone: string }, jobId: number) {
    let candidate = this.candidates.find((c) => c.email.toLowerCase() === candidateData.email.toLowerCase());
    if (!candidate) {
      candidate = {
        id: Date.now(),
        fullName: candidateData.fullName,
        email: candidateData.email,
        phone: candidateData.phone,
        consentAt: new Date().toISOString(),
      };
      this.candidates.push(candidate);
    }

    const job = this.jobs.find((j) => j.id === jobId);
    const threshold = job?.autoInviteThreshold || 80;

    // Simulate AI evaluation
    const score = Math.floor(Math.random() * 30) + 70; // 70 to 100
    const passedAuto = score >= threshold;

    const newApp: Application = {
      id: Date.now(),
      jobId,
      candidateId: candidate.id,
      submissionId: Date.now() + 1,
      status: passedAuto ? 'INTERVIEW_INVITED' : 'PENDING_HR_REVIEW',
      submittedAt: new Date().toISOString(),
      aiTotalScore: score,
      scores: [
        {
          criterionId: 1,
          criterionName: 'Độ phù hợp kỹ năng & kinh nghiệm',
          weight: 60,
          score: score,
          aiComment: 'Ứng viên có kỹ năng tương thích tốt với yêu cầu công việc.',
          evidenceQuote: 'Trích xuất từ CV: Từng đảm nhiệm các dự án trọng điểm phù hợp',
          meetsMandatory: true,
        },
        {
          criterionId: 2,
          criterionName: 'Trình độ ngoại ngữ & giao tiếp',
          weight: 40,
          score: Math.min(100, score + 5),
          aiComment: 'Khả năng tiếng Anh đáp ứng tốt yêu cầu công việc.',
          evidenceQuote: 'Trích xuất từ CV: Chứng chỉ và kinh nghiệm làm việc quốc tế',
          meetsMandatory: true,
        },
      ],
      hrNote: passedAuto
        ? 'AI tự động duyệt đạt ngưỡng -> Hệ thống đã gửi lời mời phỏng vấn'
        : 'Điểm dưới ngưỡng tự động -> Chuyển HR xét duyệt thủ công',
    };

    this.applications.unshift(newApp);

    if (passedAuto) {
      // Auto create scheduled interview
      const newInterview: Interview = {
        id: Date.now() + 2,
        applicationId: newApp.id,
        interviewerId: 2,
        startAt: new Date(Date.now() + 86400000 * 3).toISOString(),
        endAt: new Date(Date.now() + 86400000 * 3 + 3600000).toISOString(),
        status: 'SCHEDULED',
        meetLink: 'https://meet.google.com/hrchan-auto-slot',
        autoScheduled: true,
      };
      this.interviews.push(newInterview);
    }

    this.addAuditLog('DECISION', `Hồ sơ mới từ ${candidate.fullName} nộp vị trí #${jobId} (Điểm AI: ${score})`);
    this.notify();
    return newApp;
  }

  updateApplicationStatus(appId: number, status: ApplicationStatus, note?: string, rejectReason?: string) {
    const app = this.applications.find((a) => a.id === appId);
    if (app) {
      app.status = status;
      if (note) app.hrNote = note;
      if (rejectReason) app.rejectReason = rejectReason;
      this.addAuditLog('DECISION', `Cập nhật trạng thái hồ sơ #${appId} -> ${status}`, rejectReason || note);
      this.notify();
    }
  }

  // --- Interviews ---
  getInterviews() {
    return this.interviews.map((item) => {
      const app = this.getApplicationById(item.applicationId);
      const interviewer = this.users.find((u) => u.id === item.interviewerId);
      return {
        ...item,
        application: app,
        interviewerName: interviewer?.fullName || 'N/A',
      };
    });
  }

  updateInterviewStatus(interviewId: number, status: Interview['status'], note?: string) {
    const itv = this.interviews.find((i) => i.id === interviewId);
    if (itv) {
      itv.status = status;
      if (note) itv.rescheduleNote = note;
      this.addAuditLog('DECISION', `Cập nhật buổi phỏng vấn #${interviewId} -> ${status}`);
      this.notify();
    }
  }

  submitInterviewEvaluation(interviewId: number, result: 'PASSED' | 'FAILED' | 'ABSENT', note: string) {
    const itv = this.interviews.find((i) => i.id === interviewId);
    if (itv) {
      itv.status = 'COMPLETED';
      itv.result = result;
      itv.finalNote = note;

      const app = this.applications.find((a) => a.id === itv.applicationId);
      if (app) {
        if (result === 'PASSED') {
          app.status = 'INTERVIEW_PASSED';
        } else if (result === 'ABSENT') {
          app.status = 'INTERVIEW_FAILED';
          app.rejectReason = 'Ứng viên vắng mặt buổi phỏng vấn';
        } else {
          app.status = 'INTERVIEW_FAILED';
          app.rejectReason = 'Không đạt tiêu chí chuyên môn phỏng vấn';
        }
      }

      this.addAuditLog('DECISION', `Chấm kết quả phỏng vấn #${interviewId} -> ${result}`, note);
      this.notify();
    }
  }

  // --- Probations & Tasks ---
  getProbations() {
    return this.probations.map((p) => {
      const app = this.getApplicationById(p.applicationId);
      const trainee = this.users.find((u) => u.id === p.traineeId);
      const manager = this.users.find((u) => u.id === p.managerId);
      const probationTasks = this.tasks.filter((t) => t.probationId === p.id);
      return {
        ...p,
        application: app,
        traineeName: trainee?.fullName || 'N/A',
        traineeEmail: trainee?.email || 'N/A',
        managerName: manager?.fullName || 'N/A',
        tasks: probationTasks,
      };
    });
  }

  getTasksForProbation(probationId: number) {
    return this.tasks.filter((t) => t.probationId === probationId);
  }

  createProbationTask(probationId: number, taskData: { title: string; description: string; dueAt: string }) {
    const newTask: ProbationTask = {
      id: Date.now(),
      probationId,
      title: taskData.title,
      description: taskData.description,
      dueAt: taskData.dueAt,
      createdAt: new Date().toISOString(),
    };
    this.tasks.push(newTask);
    this.addAuditLog('DECISION', `Giao task mới cho đợt thử việc #${probationId}: ${newTask.title}`);
    this.notify();
    return newTask;
  }

  submitTaskDeliverable(taskId: number, content: string) {
    const task = this.tasks.find((t) => t.id === taskId);
    if (task) {
      const isLate = new Date() > new Date(task.dueAt);
      task.submission = {
        submittedAt: new Date().toISOString(),
        content,
        isLate,
      };
      this.addAuditLog('DECISION', `Nộp bài cho task #${taskId} (${isLate ? 'Nộp muộn' : 'Đúng hạn'})`);
      this.notify();
    }
  }

  gradeTask(taskId: number, result: 'PASSED' | 'FAILED', feedback: string) {
    const task = this.tasks.find((t) => t.id === taskId);
    if (task) {
      task.result = result;
      task.feedback = feedback;
      task.gradedAt = new Date().toISOString();
      this.addAuditLog('DECISION', `Đánh giá task #${taskId} -> ${result}`, feedback);
      this.notify();
    }
  }

  concludeProbation(probationId: number, status: 'PASSED' | 'FAILED', conclusionNote: string) {
    const p = this.probations.find((item) => item.id === probationId);
    if (p) {
      p.status = status;
      p.conclusionNote = conclusionNote;
      p.concludedAt = new Date().toISOString();

      const app = this.applications.find((a) => a.id === p.applicationId);
      if (app) {
        app.status = status === 'PASSED' ? 'PROBATION_PASSED' : 'PROBATION_FAILED';
      }

      this.addAuditLog('DECISION', `Kết luận đợt thử việc #${probationId} -> ${status}`, conclusionNote);
      this.notify();
    }
  }

  // --- Audit Logs ---
  getAuditLogs() {
    return this.auditLogs;
  }

  private addAuditLog(actionType: AuditLog['actionType'], details: string, reason?: string) {
    const log: AuditLog = {
      id: Date.now(),
      timestamp: new Date().toISOString(),
      actorId: this.currentUser.id,
      actorName: this.currentUser.fullName,
      actorRole: this.currentUser.roles[0] || 'UNKNOWN',
      actionType,
      target: details,
      details,
      reason,
    };
    this.auditLogs.unshift(log);
  }

  // --- Settings ---
  getSettings() {
    return this.settings;
  }

  updateSettings(newSettings: Partial<SystemSettings>) {
    this.settings = { ...this.settings, ...newSettings };
    this.addAuditLog('CONFIG', 'Cập nhật cấu hình hệ thống');
    this.notify();
  }
}

export const mockStore = new MockStore();
