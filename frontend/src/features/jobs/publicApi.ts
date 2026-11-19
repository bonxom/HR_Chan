import { apiGet } from "@/shared/services/client";
import type {
  PublicJobDetail,
  PublicJobDetailJson,
  PublicJobFilters,
  PublicJobPage,
  PublicJobPageJson,
  PublicJobSummary,
  PublicJobSummaryJson,
} from "./publicTypes";

function mapSummary(data: PublicJobSummaryJson): PublicJobSummary {
  return {
    id: data.id,
    title: data.title,
    departmentId: data.department_id,
    departmentName: data.department_name,
    headcount: data.headcount,
    workMode: data.work_mode,
    location: data.location,
    deadline: data.deadline,
  };
}

export async function listPublicJobs(
  filters: PublicJobFilters = {},
  signal?: AbortSignal,
): Promise<PublicJobPage> {
  const params = new URLSearchParams();
  params.set("page", String(filters.page ?? 1));
  params.set("page_size", String(filters.pageSize ?? 12));
  const q = filters.q?.trim();
  if (q) params.set("q", q);
  if (filters.departmentId !== undefined) params.set("department_id", String(filters.departmentId));
  const data = await apiGet<PublicJobPageJson>(`/api/v1/public/jobs?${params.toString()}`, signal);
  return {
    items: data.items.map(mapSummary),
    total: data.total,
    page: data.page,
    pageSize: data.page_size,
  };
}

export async function getPublicJob(id: number, signal?: AbortSignal): Promise<PublicJobDetail> {
  const data = await apiGet<PublicJobDetailJson>(`/api/v1/public/jobs/${id}`, signal);
  return {
    ...mapSummary(data),
    description: data.description,
    requirements: data.requirements,
    benefits: data.benefits ?? null,
  };
}
