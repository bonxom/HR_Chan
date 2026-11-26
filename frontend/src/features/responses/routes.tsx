import { ResponsePage } from "./ResponsePage";

export const responseRoutes = [
  { path: "/r", element: <ResponsePage /> },
  { path: "/r/:token", element: <ResponsePage /> },
];
