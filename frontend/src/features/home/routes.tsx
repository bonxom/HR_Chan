import type { RouteObject } from "react-router";
import { HomePage } from "./Home";

export const homeRoutes: RouteObject[] = [
  { index: true, element: <HomePage /> },
];
