import {
  ADMIN_EMAIL,
  ADMIN_PASSWORD,
  bootstrapAdmin,
  completePassword,
  ensureReferenceData,
  latestTokenFor,
  resetDatabase,
  seedDevAccounts,
  seedEmailTemplates,
  startWorker,
} from "./support";

export default async function globalSetup(): Promise<() => void> {
  resetDatabase();
  // Order matters: templates first, then queued mail, then the worker that delivers it.
  seedEmailTemplates();
  ensureReferenceData();
  bootstrapAdmin();
  const stopWorker = startWorker();
  try {
    const token = await latestTokenFor(ADMIN_EMAIL);
    await completePassword(token, ADMIN_PASSWORD);
    // Development fixtures for the one-click login panel.
    seedDevAccounts();
  } catch (error) {
    stopWorker();
    throw error;
  }
  // The worker keeps running so invitations created by tests are delivered.
  return stopWorker;
}
