import { execFileSync, spawn, spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

export const ADMIN_EMAIL = "e2e.admin@sis.hust.edu.vn";
export const ADMIN_PASSWORD = "e2e-administrator-password";
export const ADMIN_NAME = "E2E Administrator";

export const apiBaseUrl = process.env.E2E_API_URL ?? "http://localhost:8000";
const mailpitUrl = process.env.E2E_MAILPIT_URL ?? "http://localhost:8025";
const backendDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "../../../backend");

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) throw new Error(`${name} is required for browser tests`);
  return value;
}

const APPLICATION_DATABASE = "hr_chan";

function databaseName(url: string, label: string): string {
  const name = decodeURIComponent(url.replace(/[?#].*$/, "").split("/").pop() ?? "");
  if (!name) throw new Error(`${label} has no database name`);
  return name;
}

function rawPsql(sql: string): string {
  const expected = requireEnv("E2E_EXPECTED_DATABASE");
  const flags = ["-v", "ON_ERROR_STOP=1", "-t", "-A", "-c", sql];
  const container = process.env.E2E_PSQL_CONTAINER;
  const [command, args] = container
    ? ["docker", ["exec", "-i", container, "psql", "-U", "hr_chan", "-d", expected, ...flags]]
    : ["psql", [requireEnv("E2E_PSQL_URL"), ...flags]];
  return execFileSync(command, args, { encoding: "utf8" }).trim();
}

let verifiedDatabase: string | null = null;

/** Refuse to touch anything unless every DB setting and the live connection name the expected DB. */
function verifyDatabase(): void {
  const expected = requireEnv("E2E_EXPECTED_DATABASE");
  if (verifiedDatabase === expected) return;
  if (expected === APPLICATION_DATABASE) {
    throw new Error("E2E_EXPECTED_DATABASE must not be the application database");
  }
  for (const name of ["E2E_PSQL_URL", "E2E_DATABASE_URL"]) {
    if (databaseName(requireEnv(name), name) !== expected) {
      throw new Error(`${name} does not point at E2E_EXPECTED_DATABASE`);
    }
  }
  if (rawPsql("SELECT current_database()") !== expected) {
    throw new Error("Connected database differs from E2E_EXPECTED_DATABASE");
  }
  verifiedDatabase = expected;
}

/** Clear account data on the dedicated browser-test database only. */
export function resetDatabase(): void {
  psql("TRUNCATE TABLE accounts CASCADE");
}

/** Run one SQL statement on the verified browser-test database and return trimmed output. */
export function psql(sql: string): string {
  verifyDatabase();
  return rawPsql(sql);
}

function pythonCommand(args: string[]): [string, string[]] {
  const python = process.env.E2E_PYTHON;
  return python ? [python, args] : ["uv", ["run", "python", ...args]];
}

function cliEnvironment(): NodeJS.ProcessEnv {
  verifyDatabase();
  // Account emails are queued in the outbox and delivered by the worker over SMTP (Mailpit).
  const optional = (name: string, source: string): NodeJS.ProcessEnv =>
    process.env[source] ? { [name]: process.env[source] } : {};
  return {
    ...process.env,
    DATABASE_URL: requireEnv("E2E_DATABASE_URL"),
    JWT_SECRET: requireEnv("E2E_JWT_SECRET"),
    LIMITER_SECRET: requireEnv("E2E_LIMITER_SECRET"),
    OUTBOX_ENCRYPTION_KEY: requireEnv("E2E_OUTBOX_ENCRYPTION_KEY"),
    EMAIL_PROVIDER: "smtp",
    SMTP_HOST: process.env.E2E_SMTP_HOST ?? "localhost",
    SMTP_PORT: process.env.E2E_SMTP_PORT ?? "1025",
    FRONTEND_URL: process.env.E2E_BASE_URL ?? "http://localhost:5173",
    EMAIL_OUTBOX_INTERVAL_SECONDS: "2",
    ...optional("CV_STORAGE_DIR", "E2E_CV_STORAGE_DIR"),
    ...optional("CV_ENCRYPTION_KEY", "E2E_CV_ENCRYPTION_KEY"),
  };
}

function runCli(args: string[], extraEnv: NodeJS.ProcessEnv = {}): void {
  const [command, commandArgs] = pythonCommand(["-m", "app.cli", ...args]);
  execFileSync(command, commandArgs, {
    cwd: backendDir,
    env: { ...cliEnvironment(), ...extraEnv },
    stdio: "pipe",
  });
}

/** Templates must exist before any email is queued (bootstrap, invitations, OTP). */
export function seedEmailTemplates(): void {
  runCli(["seed-email-templates"]);
}

/** Departments and the default threshold a published job needs; idempotent. */
export function ensureReferenceData(): void {
  psql("INSERT INTO departments (name) VALUES ('Phòng Kỹ thuật') ON CONFLICT (name) DO NOTHING");
  psql(
    "INSERT INTO system_settings (key, value, default_value, min_value, max_value, unit) " +
      "VALUES ('auto_invite_threshold', 70, 70, 0, 100, 'điểm') ON CONFLICT (key) DO NOTHING",
  );
}

/** Long-running outbox worker for the browser-test database; returns a stop function. */
export function startWorker(): () => void {
  const [command, commandArgs] = pythonCommand(["-m", "app.worker"]);
  const child = spawn(command, commandArgs, {
    cwd: backendDir,
    env: cliEnvironment(),
    stdio: "ignore",
    windowsHide: true,
  });
  // A missing interpreter must not crash the runner; the setup then fails at the mail wait.
  child.on("error", () => undefined);
  return () => {
    if (child.pid === undefined || child.exitCode !== null) return;
    if (process.platform === "win32") {
      // `uv run` starts python as a child; stop the whole tree.
      spawnSync("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
    } else {
      child.kill("SIGTERM");
    }
  };
}

export function bootstrapAdmin(): void {
  runCli(["bootstrap-admin", "--email", ADMIN_EMAIL, "--name", ADMIN_NAME]);
}

export function seedDevAccounts(): void {
  runCli(["seed-dev-accounts"], { DEV_SEED_ENABLED: "true" });
}

interface MailpitMessage {
  ID: string;
  Subject: string;
  To: Array<{ Address: string }>;
  Created: string;
}

/** Shared Mailpit keeps older runs: ignore messages created before E2E_MAIL_AFTER (ISO), if set. */
function isRecentFor(item: MailpitMessage, email: string): boolean {
  const cutoff = process.env.E2E_MAIL_AFTER ? Date.parse(process.env.E2E_MAIL_AFTER) : NaN;
  if (!Number.isNaN(cutoff) && !(Date.parse(item.Created) >= cutoff)) return false;
  return item.To.some((recipient) => recipient.Address === email);
}

// Messages already handed out: a later unlock/recovery must wait for its own new email.
const usedMessageIds = new Set<string>();

export async function latestTokenFor(email: string): Promise<string> {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const response = await fetch(`${mailpitUrl}/api/v1/messages?limit=20`);
    const payload = (await response.json()) as { messages: MailpitMessage[] };
    const message = payload.messages.find(
      (item) => !usedMessageIds.has(item.ID) && isRecentFor(item, email),
    );
    if (message) {
      const detail = await fetch(`${mailpitUrl}/api/v1/message/${message.ID}`);
      const body = await detail.text();
      const match = body.match(/#token=([A-Za-z0-9_-]+)/);
      if (match) {
        usedMessageIds.add(message.ID);
        return match[1];
      }
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`No invitation email for ${email}`);
}

/** Latest 6-digit apply code mailed to `email`; never log or attach the returned value. */
export async function latestOtpFor(email: string): Promise<string> {
  for (let attempt = 0; attempt < 40; attempt += 1) {
    const response = await fetch(`${mailpitUrl}/api/v1/messages?limit=20`);
    const payload = (await response.json()) as { messages: MailpitMessage[] };
    const message = payload.messages.find((item) => isRecentFor(item, email));
    if (message) {
      const detail = (await (await fetch(`${mailpitUrl}/api/v1/message/${message.ID}`)).json()) as {
        Text?: string;
      };
      const match = detail.Text?.match(/\b(\d{6})\b/);
      if (match) return match[1];
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error("No verification email arrived for the test candidate");
}

/** Smallest valid PDF with a real text layer (ASCII only, no parentheses). */
export function minimalPdf(text: string): Buffer {
  const stream = `BT /F1 14 Tf 72 720 Td (${text}) Tj ET`;
  const objects = [
    "<< /Type /Catalog /Pages 2 0 R >>",
    "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`,
    "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
  ];
  let body = "%PDF-1.4\n";
  const offsets: number[] = [];
  objects.forEach((object, index) => {
    offsets.push(body.length);
    body += `${index + 1} 0 obj\n${object}\nendobj\n`;
  });
  const xref = body.length;
  body += `xref\n0 ${objects.length + 1}\n0000000000 65535 f \n`;
  for (const offset of offsets) body += `${String(offset).padStart(10, "0")} 00000 n \n`;
  body += `trailer\n<< /Size ${objects.length + 1} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`;
  return Buffer.from(body, "latin1");
}

const browserOrigin = process.env.E2E_BASE_URL ?? "http://localhost:5173";

export async function postJson(path: string, body: unknown): Promise<Response> {
  return fetch(`${apiBaseUrl}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Origin: browserOrigin },
    body: JSON.stringify(body),
  });
}

export async function completePassword(token: string, password: string): Promise<void> {
  const response = await postJson("/api/v1/auth/password/complete", {
    token,
    new_password: password,
  });
  if (!response.ok) throw new Error(`Password completion failed: ${response.status}`);
}

/** Publish a job through the HR API (dev HR persona) and return its id. */
export async function createOpenJob(title: string): Promise<number> {
  const token = await loginViaApi("dev.hr@sis.hust.edu.vn", "dev-only-password");
  const headers = {
    Authorization: `Bearer ${token}`,
    Origin: browserOrigin,
    "Content-Type": "application/json",
  };
  const departments = (await (await fetch(`${apiBaseUrl}/api/v1/departments`, { headers })).json()) as {
    id: number;
  }[];
  const interviewers = (await (await fetch(`${apiBaseUrl}/api/v1/interviewers`, { headers })).json()) as {
    id: string;
  }[];
  const deadline = new Date(Date.now() + 30 * 86_400_000).toISOString().slice(0, 10);
  const response = await fetch(`${apiBaseUrl}/api/v1/jobs`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      title,
      department_id: departments[0].id,
      description: "Mô tả công việc cho kiểm thử trình duyệt.",
      requirements: "Python, SQL.",
      benefits: "Bảo hiểm đầy đủ.",
      headcount: 1,
      work_mode: "Toàn thời gian",
      location: "Hà Nội",
      deadline,
      publish: true,
      criteria: {
        criteria: [
          { name: "Kinh nghiệm", description: "Từ 2 năm", weight: 60 },
          { name: "Tiếng Anh", description: "Đọc hiểu tài liệu", weight: 40 },
        ],
        interviewer_ids: interviewers.slice(0, 1).map((item) => item.id),
      },
    }),
  });
  if (!response.ok) throw new Error(`Job creation failed: ${response.status}`);
  return ((await response.json()) as { id: number }).id;
}

export async function loginViaApi(email: string, password: string): Promise<string> {
  const response = await postJson("/api/v1/auth/login", { email, password });
  if (!response.ok) throw new Error(`API login failed: ${response.status}`);
  const payload = (await response.json()) as { access_token: string };
  return payload.access_token;
}
