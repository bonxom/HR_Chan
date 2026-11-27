// Dụng cụ test dùng chung cho màn hình pipeline hồ sơ (không chứa test).
import { render } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router";
import { AuthProvider } from "@/features/auth/AuthProvider";
import { jsonResponse, type RecordedRequest, type RouteHandler } from "@/test/apiStub";
import { ToastContainer } from "@/shared/components/ui/Toast";
import { ApplicationPipeline } from "./ApplicationPipeline";

/** `gcTime` > 0 keeps closed-modal data cached, as in the app, to test stale reopen behaviour. */
export function renderPipeline({ gcTime = 0 }: { gcTime?: number } = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false, gcTime } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={["/app/hr/applications"]}>
          <ApplicationPipeline />
          <ToastContainer />
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  );
}

export const params = (request: RecordedRequest) => new URL(request.path, "http://localhost").searchParams;

export const BY_STATUS: Record<string, number> = {
  SCORING: 1,
  PENDING_HR_REVIEW: 4,
  INTERVIEW_INVITED: 2,
  INTERVIEW_CONFIRMED: 1,
  AWAITING_INTERVIEW_RESULT: 3,
  REJECTED: 1,
};

/** Body of GET /applications/counts; total is the sum of by_status, as on the backend. */
export function countsJson(byStatus: Record<string, number> = BY_STATUS, overdue = 0) {
  const total = Object.values(byStatus).reduce((sum, value) => sum + value, 0);
  return { total, overdue, by_status: byStatus };
}

export const COUNTS_ROUTE = "GET /api/v1/applications/counts";

/** Handler for the list route (kept as a named wrapper so tests read the same as before). */
export function applicationsRoute(
  listPage: (request: RecordedRequest) => Response | Promise<Response>,
): RouteHandler {
  return listPage;
}

export const countsRoute = (body = countsJson()): RouteHandler => () => jsonResponse(body);
