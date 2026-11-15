import {
  ADMIN_EMAIL,
  ADMIN_PASSWORD,
  bootstrapAdmin,
  completePassword,
  latestTokenFor,
  resetDatabase,
  seedDevAccounts,
} from "./support";

export default async function globalSetup(): Promise<void> {
  resetDatabase();
  bootstrapAdmin();
  const token = await latestTokenFor(ADMIN_EMAIL);
  await completePassword(token, ADMIN_PASSWORD);
  // Development fixtures for the one-click login panel.
  seedDevAccounts();
}
