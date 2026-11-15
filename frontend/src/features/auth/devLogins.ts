/**
 * Development-only quick logins.
 *
 * The panel is gated by `devLoginsEnabled` (false in production builds) and asks the
 * backend's development-only `/auth/dev-login` route to open a normal session for a
 * fixed persona. Password changes on the fixture accounts no longer break the buttons.
 */
export interface DevLogin {
  id: string;
  label: string;
  note: string;
  email: string;
}

export const devLoginsEnabled = import.meta.env.DEV;

export const DEV_LOGINS: DevLogin[] = [
  {
    id: "admin",
    label: "Admin",
    note: "Quản trị",
    email: "dev.admin@sis.hust.edu.vn",
  },
  {
    id: "hr",
    label: "HR",
    note: "Tuyển dụng",
    email: "dev.hr@sis.hust.edu.vn",
  },
  {
    id: "interviewer",
    label: "Interviewer",
    note: "Phỏng vấn",
    email: "dev.interviewer@sis.hust.edu.vn",
  },
  {
    id: "manager",
    label: "Manager",
    note: "Quản lý",
    email: "dev.manager@sis.hust.edu.vn",
  },
  {
    id: "trainee",
    label: "Trainee",
    note: "Thử việc",
    email: "dev.trainee@sis.hust.edu.vn",
  },
];
