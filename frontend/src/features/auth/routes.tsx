import type { RouteObject } from "react-router";
import { AccountPage } from "./AccountPage";
import { CompletePasswordPage } from "./CompletePasswordPage";
import { LoginPage } from "./LoginPage";
import { RecoveryPage } from "./RecoveryPage";

export const authEntryRoutes: RouteObject[] = [
  { path: "/login", element: <LoginPage /> },
  { path: "/forgot-password", element: <RecoveryPage /> },
  { path: "/set-password", element: <CompletePasswordPage /> },
];

export const accountRoutes: RouteObject[] = [{ path: "account", element: <AccountPage /> }];
