// DTO công khai: chỉ các trường backend cho phép lộ ra (không tiêu chí, người phỏng vấn, trạng thái).
export interface PublicJobSummaryJson {
  id: number;
  title: string;
  department_id: number;
  department_name: string;
  headcount: number;
  work_mode: string;
  location: string;
  deadline: string;
}

export interface PublicJobDetailJson extends PublicJobSummaryJson {
  description: string;
  requirements: string;
  benefits: string | null;
}

export interface PublicJobPageJson {
  items: PublicJobSummaryJson[];
  total: number;
  page: number;
  page_size: number;
}

export interface PublicJobSummary {
  id: number;
  title: string;
  departmentId: number;
  departmentName: string;
  headcount: number;
  workMode: string;
  location: string;
  deadline: string;
}

export interface PublicJobDetail extends PublicJobSummary {
  description: string;
  requirements: string;
  benefits: string | null;
}

export interface PublicJobPage {
  items: PublicJobSummary[];
  total: number;
  page: number;
  pageSize: number;
}

export interface PublicJobFilters {
  page?: number;
  pageSize?: number;
  q?: string;
  departmentId?: number;
}
