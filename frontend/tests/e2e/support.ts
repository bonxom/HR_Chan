import { execFileSync } from "node:child_process";
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

/** Clear account data on the dedicated browser-test database only. */
export function resetDatabase(): void {
  const psqlUrl = requireEnv("E2E_PSQL_URL");
  execFileSync("psql", [psqlUrl, "-v", "ON_ERROR_STOP=1", "-c", "TRUNCATE TABLE accounts CASCADE"]);
}

function cliEnvironment(): NodeJS.ProcessEnv {
  return {
    ...process.env,
    DATABASE_URL: requireEnv("E2E_DATABASE_URL"),
    JWT_SECRET: requireEnv("E2E_JWT_SECRET"),
    LIMITER_SECRET: requireEnv("E2E_LIMITER_SECRET"),
    SMTP_HOST: process.env.E2E_SMTP_HOST ?? "localhost",
    SMTP_PORT: process.env.E2E_SMTP_PORT ?? "1025",
    FRONTEND_URL: process.env.E2E_BASE_URL ?? "http://localhost:5173",
  };
}

export function bootstrapAdmin(): void {
  execFileSync(
    "uv",
    [
      "run",
      "python",
      "-m",
      "app.cli",
      "bootstrap-admin",
      "--email",
      ADMIN_EMAIL,
      "--name",
      ADMIN_NAME,
    ],
    { cwd: backendDir, env: cliEnvironment(), stdio: "pipe" },
  );
}

export function seedDevAccounts(): void {
  execFileSync("uv", ["run", "python", "-m", "app.cli", "seed-dev-accounts"], {
    cwd: backendDir,
    env: { ...cliEnvironment(), DEV_SEED_ENABLED: "true" },
    stdio: "pipe",
  });
}

interface MailpitMessage {
  ID: string;
  Subject: string;
  To: Array<{ Address: string }>;
}

export async function latestTokenFor(email: string): Promise<string> {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    const response = await fetch(`${mailpitUrl}/api/v1/messages?limit=20`);
    const payload = (await response.json()) as { messages: MailpitMessage[] };
    const message = payload.messages.find((item) =>
      item.To.some((recipient) => recipient.Address === email),
    );
    if (message) {
      const detail = await fetch(`${mailpitUrl}/api/v1/message/${message.ID}`);
      const body = await detail.text();
      const match = body.match(/#token=([A-Za-z0-9_-]+)/);
      if (match) return match[1];
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  throw new Error(`No invitation email for ${email}`);
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

export async function loginViaApi(email: string, password: string): Promise<string> {
  const response = await postJson("/api/v1/auth/login", { email, password });
  if (!response.ok) throw new Error(`API login failed: ${response.status}`);
  const payload = (await response.json()) as { access_token: string };
  return payload.access_token;
}
