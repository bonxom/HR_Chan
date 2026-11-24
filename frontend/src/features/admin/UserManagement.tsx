import { useMemo, useState } from "react";
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Lock, MailPlus, Pencil, ShieldBan, Unlock, UserPlus } from "lucide-react";
import { Badge } from "@/shared/components/ui/Badge";
import { Button } from "@/shared/components/ui/Button";
import { Card } from "@/shared/components/ui/Card";
import { Input } from "@/shared/components/ui/Input";
import { Modal } from "@/shared/components/ui/Modal";
import { showToast } from "@/shared/components/ui/Toast";
import { isDevBuild } from "@/configs/env";
import { useAuth } from "@/features/auth/AuthProvider";
import type { AccountStatus, AccountType, AuthAccount, EmployeeRole } from "@/features/auth/types";
import {
  createAccount,
  describeAdminError,
  disableAccount,
  listAccounts,
  lockAccount,
  replaceRoles,
  resendInvitation,
  unlockAccount,
} from "./api";
import type { AccountListFilters, CreateAccountInput } from "./types";

const EMPLOYEE_ROLES: EmployeeRole[] = ["HR", "INTERVIEWER", "DEPT_MANAGER", "PROBATION"];

// Development only: the local mailbox keeps the reset link easy to find.
const MAILBOX_HINT = isDevBuild
  ? " (dev: mở Mailpit http://127.0.0.1:8025 để lấy liên kết)"
  : "";

const ROLE_LABELS: Record<EmployeeRole, string> = {
  HR: "Tuyển dụng (HR)",
  INTERVIEWER: "Người phỏng vấn",
  DEPT_MANAGER: "Quản lý bộ phận",
  PROBATION: "Thử việc",
};

const STATUS_LABELS: Record<AccountStatus, string> = {
  PENDING_SETUP: "Chờ thiết lập",
  ACTIVE: "Đang hoạt động",
  LOCKED: "Đã khóa",
  PASSWORD_RESET_REQUIRED: "Cần đặt lại mật khẩu",
  DISABLED: "Đã vô hiệu hóa",
};

const STATUS_VARIANTS: Record<
  AccountStatus,
  "success" | "warning" | "danger" | "info" | "neutral" | "purple"
> = {
  PENDING_SETUP: "info",
  ACTIVE: "success",
  LOCKED: "warning",
  PASSWORD_RESET_REQUIRED: "purple",
  DISABLED: "neutral",
};

export function applyRoleSelection(
  current: EmployeeRole[],
  role: EmployeeRole,
  checked: boolean,
): EmployeeRole[] {
  if (!checked) return current.filter((item) => item !== role);
  if (role === "PROBATION") return ["PROBATION"];
  const withoutProbation = current.filter((item) => item !== "PROBATION");
  return withoutProbation.includes(role) ? withoutProbation : [...withoutProbation, role];
}

function RoleCheckboxes({
  value,
  onChange,
  namePrefix,
}: {
  value: EmployeeRole[];
  onChange: (roles: EmployeeRole[]) => void;
  namePrefix: string;
}) {
  return (
    <fieldset className="space-y-2">
      <legend className="text-xs font-semibold text-slate-600">
        Vai trò nghiệp vụ
      </legend>
      {EMPLOYEE_ROLES.map((role) => (
        <label key={role} className="flex items-center gap-2 text-sm text-slate-700">
          <input
            type="checkbox"
            name={`${namePrefix}-${role}`}
            checked={value.includes(role)}
            onChange={(event) => onChange(applyRoleSelection(value, role, event.target.checked))}
          />
          {ROLE_LABELS[role]}
        </label>
      ))}
      <p className="text-xs text-slate-500">
        PROBATION phải là vai trò duy nhất khi được chọn. Nhân viên cần ít nhất một vai trò.
      </p>
    </fieldset>
  );
}

export function UserManagement() {
  const { account: currentAccount, authorized } = useAuth();
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState<AccountListFilters>({});
  const [createOpen, setCreateOpen] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [deliveryWarning, setDeliveryWarning] = useState<string | null>(null);
  const [roleTarget, setRoleTarget] = useState<AuthAccount | null>(null);
  const [reasonAction, setReasonAction] = useState<{ account: AuthAccount; kind: "lock" | "disable" } | null>(
    null,
  );
  const [reason, setReason] = useState("");
  const [form, setForm] = useState<CreateAccountInput>({
    fullName: "",
    email: "",
    accountType: "EMPLOYEE",
    roles: ["HR"],
  });
  const [roleDraft, setRoleDraft] = useState<EmployeeRole[]>([]);

  const accountsQuery = useInfiniteQuery({
    queryKey: ["accounts", filters.status ?? null, filters.accountType ?? null],
    queryFn: ({ pageParam }) =>
      authorized((token) =>
        listAccounts(token, {
          status: filters.status,
          accountType: filters.accountType,
          cursor: pageParam ?? undefined,
        }),
      ),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.nextCursor,
  });

  const accounts = useMemo(
    () => accountsQuery.data?.pages.flatMap((page) => page.items) ?? [],
    [accountsQuery.data],
  );

  const refreshAccounts = () => queryClient.invalidateQueries({ queryKey: ["accounts"] });

  const createMutation = useMutation({
    mutationFn: (input: CreateAccountInput) => authorized((token) => createAccount(token, input)),
    onSuccess: (result) => {
      setCreateOpen(false);
      setDeliveryWarning(
        result.emailDelivery === "failed"
          ? `Đã tạo tài khoản ${result.account.email} nhưng email lời mời chưa gửi được. Hãy dùng "Gửi lại lời mời" cho tài khoản đang chờ thiết lập.`
          : null,
      );
      setForm({ fullName: "", email: "", accountType: "EMPLOYEE", roles: ["HR"] });
      void refreshAccounts();
      showToast({ type: "success", message: "Đã tạo tài khoản và gửi lời mời thiết lập mật khẩu." });
    },
    onError: (error) => setFormError(describeAdminError(error)),
  });

  const rolesMutation = useMutation({
    mutationFn: ({ id, roles }: { id: string; roles: EmployeeRole[] }) =>
      authorized((token) => replaceRoles(token, id, roles)),
    onSuccess: () => {
      setRoleTarget(null);
      void refreshAccounts();
      showToast({ type: "success", message: "Đã cập nhật vai trò nghiệp vụ." });
    },
    onError: (error) => setFormError(describeAdminError(error)),
  });

  const lockMutation = useMutation({
    mutationFn: ({ id, value }: { id: string; value: string }) =>
      authorized((token) => lockAccount(token, id, value)),
    onSuccess: () => {
      setReasonAction(null);
      setReason("");
      void refreshAccounts();
      showToast({ type: "success", message: "Đã khóa tài khoản và thu hồi các phiên đăng nhập." });
    },
    onError: (error) => setFormError(describeAdminError(error)),
  });

  const unlockMutation = useMutation({
    mutationFn: (id: string) => authorized((token) => unlockAccount(token, id)),
    onSuccess: (result) => {
      setDeliveryWarning(
        result.emailDelivery === "failed"
          ? "Đã mở khóa nhưng email đặt lại mật khẩu chưa gửi được. Hãy thử lại sau ít phút."
          : null,
      );
      void refreshAccounts();
      showToast({ type: "success", message: "Đã mở khóa tài khoản." });
    },
    onError: (error) => showToast({ type: "error", message: describeAdminError(error) }),
  });

  const disableMutation = useMutation({
    mutationFn: ({ id, value }: { id: string; value: string }) =>
      authorized((token) => disableAccount(token, id, value)),
    onSuccess: () => {
      setReasonAction(null);
      setReason("");
      void refreshAccounts();
      showToast({ type: "success", message: "Đã vô hiệu hóa tài khoản." });
    },
    onError: (error) => setFormError(describeAdminError(error)),
  });

  const resendMutation = useMutation({
    mutationFn: (id: string) => authorized((token) => resendInvitation(token, id)),
    onSuccess: (result) => {
      setDeliveryWarning(
        result.emailDelivery === "failed" ? "Email vẫn chưa gửi được. Vui lòng thử lại sau." : null,
      );
      showToast({ type: "success", message: "Đã gửi lại email." });
    },
    onError: (error) => showToast({ type: "error", message: describeAdminError(error) }),
  });

  const notice = resendMutation.isSuccess
    ? `Đã gửi email đặt lại mật khẩu.${MAILBOX_HINT}`
    : unlockMutation.isSuccess
      ? `Đã mở khóa; người dùng phải đặt lại mật khẩu.${MAILBOX_HINT}`
      : null;

  function dismissNotice() {
    resendMutation.reset();
    unlockMutation.reset();
  }

  function openCreate() {
    setFormError(null);
    setCreateOpen(true);
  }

  function submitCreate() {
    setFormError(null);
    const roles = form.accountType === "ADMIN" ? [] : form.roles;
    if (!form.fullName.trim() || !form.email.trim()) {
      setFormError("Vui lòng nhập họ tên và email.");
      return;
    }
    if (form.accountType === "EMPLOYEE" && roles.length === 0) {
      setFormError("Nhân viên cần ít nhất một vai trò nghiệp vụ.");
      return;
    }
    createMutation.mutate({ ...form, roles });
  }

  function submitReason() {
    if (!reasonAction) return;
    if (!reason.trim()) {
      setFormError("Bắt buộc nhập lý do.");
      return;
    }
    if (reasonAction.kind === "lock") {
      lockMutation.mutate({ id: reasonAction.account.id, value: reason.trim() });
    } else {
      disableMutation.mutate({ id: reasonAction.account.id, value: reason.trim() });
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-extrabold text-slate-900">Quản lý Tài khoản &amp; Phân quyền</h2>
          <p className="text-xs text-slate-500 mt-1">
            Tạo tài khoản, thay thế vai trò, khóa/mở khóa và vô hiệu hóa tài khoản nội bộ.
          </p>
        </div>
        <Button onClick={openCreate} leftIcon={<UserPlus className="w-4 h-4" />}>
          Thêm tài khoản mới
        </Button>
      </div>

      {notice && (
        <div
          role="status"
          className="flex items-start justify-between gap-3 rounded-xl border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900"
        >
          <span>{notice}</span>
          <button
            type="button"
            className="text-xs font-semibold text-sky-700 hover:underline"
            onClick={dismissNotice}
          >
            Đóng
          </button>
        </div>
      )}

      {deliveryWarning && (
        <div role="alert" className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          {deliveryWarning}
        </div>
      )}

      <Card className="p-4">
        <div className="flex flex-wrap items-center gap-3 text-xs">
          <label className="flex items-center gap-2 text-slate-600">
            Trạng thái
            <select
              aria-label="Lọc theo trạng thái"
              className="bg-white border border-slate-300 rounded-lg px-2 py-1.5"
              value={filters.status ?? ""}
              onChange={(event) =>
                setFilters((current) => ({
                  ...current,
                  status: (event.target.value || undefined) as AccountStatus | undefined,
                }))
              }
            >
              <option value="">Tất cả</option>
              {Object.entries(STATUS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-slate-600">
            Loại tài khoản
            <select
              aria-label="Lọc theo loại tài khoản"
              className="bg-white border border-slate-300 rounded-lg px-2 py-1.5"
              value={filters.accountType ?? ""}
              onChange={(event) =>
                setFilters((current) => ({
                  ...current,
                  accountType: (event.target.value || undefined) as AccountType | undefined,
                }))
              }
            >
              <option value="">Tất cả</option>
              <option value="EMPLOYEE">Nhân viên</option>
              <option value="ADMIN">Quản trị</option>
            </select>
          </label>
        </div>
      </Card>

      <Card className="p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs text-slate-500">
            <tr>
              <th className="px-4 py-3">Tài khoản</th>
              <th className="px-4 py-3">Loại</th>
              <th className="px-4 py-3">Vai trò</th>
              <th className="px-4 py-3">Trạng thái</th>
              <th className="px-4 py-3 text-right">Thao tác</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {accountsQuery.isLoading && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                  Đang tải danh sách tài khoản…
                </td>
              </tr>
            )}
            {accountsQuery.isError && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-rose-600" role="alert">
                  {describeAdminError(accountsQuery.error)}
                </td>
              </tr>
            )}
            {!accountsQuery.isLoading && accounts.length === 0 && (
              <tr>
                <td colSpan={5} className="px-4 py-6 text-center text-slate-500">
                  Chưa có tài khoản phù hợp.
                </td>
              </tr>
            )}
            {accounts.map((account) => {
              const isSelf = account.id === currentAccount?.id;
              const canResend =
                account.status === "PENDING_SETUP" ||
                account.status === "PASSWORD_RESET_REQUIRED";
              return (
                <tr key={account.id} data-testid={`account-row-${account.email}`}>
                  <td className="px-4 py-3">
                    <div className="font-semibold text-slate-900">{account.fullName}</div>
                    <div className="text-xs text-slate-500">{account.email}</div>
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-600">
                    {account.accountType === "ADMIN" ? "Quản trị" : "Nhân viên"}
                  </td>
                  <td className="px-4 py-3 text-xs text-slate-600">
                    {account.roles.length
                      ? account.roles.map((role) => ROLE_LABELS[role] ?? role).join(", ")
                      : "—"}
                  </td>
                  <td className="px-4 py-3">
                    <Badge variant={STATUS_VARIANTS[account.status] ?? "neutral"}>
                      {STATUS_LABELS[account.status]}
                    </Badge>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex flex-wrap justify-end gap-2">
                      {account.accountType === "EMPLOYEE" && account.status !== "DISABLED" && (
                        <Button
                          size="sm"
                          variant="ghost"
                          leftIcon={<Pencil className="w-3.5 h-3.5" />}
                          onClick={() => {
                            setFormError(null);
                            setRoleDraft(account.roles);
                            setRoleTarget(account);
                          }}
                        >
                          Vai trò
                        </Button>
                      )}
                      {canResend && (
                        <Button
                          size="sm"
                          variant="ghost"
                          leftIcon={<MailPlus className="w-3.5 h-3.5" />}
                          onClick={() => resendMutation.mutate(account.id)}
                        >
                          Gửi lại lời mời
                        </Button>
                      )}
                      {account.status === "LOCKED" && (
                        <Button
                          size="sm"
                          variant="outline"
                          leftIcon={<Unlock className="w-3.5 h-3.5" />}
                          onClick={() => unlockMutation.mutate(account.id)}
                        >
                          Mở khóa
                        </Button>
                      )}
                      {account.status === "ACTIVE" && (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={isSelf}
                          leftIcon={<Lock className="w-3.5 h-3.5" />}
                          onClick={() => {
                            setFormError(null);
                            setReason("");
                            setReasonAction({ account, kind: "lock" });
                          }}
                        >
                          Khóa
                        </Button>
                      )}
                      {account.status !== "DISABLED" && (
                        <Button
                          size="sm"
                          variant="danger"
                          disabled={isSelf}
                          leftIcon={<ShieldBan className="w-3.5 h-3.5" />}
                          onClick={() => {
                            setFormError(null);
                            setReason("");
                            setReasonAction({ account, kind: "disable" });
                          }}
                        >
                          Vô hiệu hóa
                        </Button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        {accountsQuery.hasNextPage && (
          <div className="p-4 border-t border-slate-100 text-center">
            <Button
              variant="outline"
              size="sm"
              isLoading={accountsQuery.isFetchingNextPage}
              onClick={() => void accountsQuery.fetchNextPage()}
            >
              Tải thêm
            </Button>
          </div>
        )}
      </Card>

      <Modal isOpen={createOpen} onClose={() => setCreateOpen(false)} title="Tạo tài khoản mới">
        <div className="space-y-4 p-6">
          <Input
            label="Họ và tên"
            name="full-name"
            value={form.fullName}
            onChange={(event) => setForm((current) => ({ ...current, fullName: event.target.value }))}
          />
          <Input
            label="Email công ty"
            name="email"
            type="email"
            value={form.email}
            onChange={(event) => setForm((current) => ({ ...current, email: event.target.value }))}
            helperText="Chỉ chấp nhận email trên tên miền sis.hust.edu.vn."
          />
          <fieldset className="space-y-2">
            <legend className="text-xs font-semibold text-slate-600">
              Loại tài khoản
            </legend>
            {(["EMPLOYEE", "ADMIN"] as AccountType[]).map((type) => (
              <label key={type} className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="radio"
                  name="account-type"
                  value={type}
                  checked={form.accountType === type}
                  onChange={() =>
                    setForm((current) => ({
                      ...current,
                      accountType: type,
                      roles: type === "ADMIN" ? [] : current.roles.length ? current.roles : ["HR"],
                    }))
                  }
                />
                {type === "ADMIN" ? "Quản trị (không có vai trò nghiệp vụ)" : "Nhân viên"}
              </label>
            ))}
          </fieldset>
          {form.accountType === "EMPLOYEE" && (
            <RoleCheckboxes
              value={form.roles}
              onChange={(roles) => setForm((current) => ({ ...current, roles }))}
              namePrefix="create-role"
            />
          )}
          {formError && (
            <p role="alert" className="text-sm text-rose-600">
              {formError}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              Hủy
            </Button>
            <Button isLoading={createMutation.isPending} onClick={submitCreate}>
              Tạo &amp; gửi lời mời
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={roleTarget !== null}
        onClose={() => setRoleTarget(null)}
        title={`Thay thế vai trò — ${roleTarget?.fullName ?? ""}`}
      >
        <div className="space-y-4 p-6">
          <RoleCheckboxes value={roleDraft} onChange={setRoleDraft} namePrefix="edit-role" />
          {formError && (
            <p role="alert" className="text-sm text-rose-600">
              {formError}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setRoleTarget(null)}>
              Hủy
            </Button>
            <Button
              isLoading={rolesMutation.isPending}
              onClick={() => {
                if (!roleTarget) return;
                if (roleDraft.length === 0) {
                  setFormError("Nhân viên cần ít nhất một vai trò nghiệp vụ.");
                  return;
                }
                rolesMutation.mutate({ id: roleTarget.id, roles: roleDraft });
              }}
            >
              Lưu vai trò
            </Button>
          </div>
        </div>
      </Modal>

      <Modal
        isOpen={reasonAction !== null}
        onClose={() => setReasonAction(null)}
        title={
          reasonAction?.kind === "lock"
            ? `Khóa tài khoản — ${reasonAction.account.fullName}`
            : `Vô hiệu hóa — ${reasonAction?.account.fullName ?? ""}`
        }
      >
        <div className="space-y-4 p-6">
          <Input
            label="Lý do (bắt buộc)"
            name="reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            helperText="Lý do được ghi vào nhật ký kiểm toán."
          />
          {formError && (
            <p role="alert" className="text-sm text-rose-600">
              {formError}
            </p>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="outline" onClick={() => setReasonAction(null)}>
              Hủy
            </Button>
            <Button
              variant={reasonAction?.kind === "disable" ? "danger" : "primary"}
              isLoading={lockMutation.isPending || disableMutation.isPending}
              onClick={submitReason}
            >
              Xác nhận
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  );
}
