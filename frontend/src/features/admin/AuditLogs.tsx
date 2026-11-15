import { useState } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { Badge } from "@/shared/components/ui/Badge";
import { Button } from "@/shared/components/ui/Button";
import { Card } from "@/shared/components/ui/Card";
import { Input } from "@/shared/components/ui/Input";
import { useAuth } from "@/features/auth/AuthProvider";
import { describeAdminError, listAuditEvents } from "./api";
import type { AuditFilters } from "./types";

function summary(value: Record<string, unknown>): string {
  const entries = Object.entries(value);
  if (entries.length === 0) return "—";
  return entries
    .map(([key, item]) => `${key}: ${Array.isArray(item) ? item.join("|") : String(item)}`)
    .join(" · ");
}

export function AuditLogs() {
  const { authorized } = useAuth();
  const [filters, setFilters] = useState<AuditFilters>({});
  const [actionInput, setActionInput] = useState("");
  const [actorInput, setActorInput] = useState("");
  const [targetInput, setTargetInput] = useState("");

  const eventsQuery = useInfiniteQuery({
    queryKey: ["audit-events", filters],
    queryFn: ({ pageParam }) =>
      authorized((token) => listAuditEvents(token, { ...filters, cursor: pageParam ?? undefined })),
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.nextCursor,
  });

  const events = eventsQuery.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-extrabold text-slate-900 flex items-center gap-2">
          <ShieldCheck className="w-5 h-5 text-emerald-600" />
          Nhật ký kiểm toán
        </h2>
        <p className="text-xs text-slate-500 mt-1">
          Chỉ hiển thị siêu dữ liệu thật do backend ghi nhận: hành động, kết quả, đối tượng và thời
          điểm. Nhật ký không thể sửa hoặc xóa.
        </p>
      </div>

      <Card className="p-4">
        <form
          className="grid grid-cols-1 sm:grid-cols-4 gap-3 items-end"
          onSubmit={(event) => {
            event.preventDefault();
            setFilters({
              action: actionInput.trim() || undefined,
              actorId: actorInput.trim() || undefined,
              targetId: targetInput.trim() || undefined,
            });
          }}
        >
          <Input
            label="Hành động"
            name="action-filter"
            placeholder="account.created"
            value={actionInput}
            onChange={(event) => setActionInput(event.target.value)}
          />
          <Input
            label="Actor ID"
            name="actor-filter"
            placeholder="UUID"
            value={actorInput}
            onChange={(event) => setActorInput(event.target.value)}
          />
          <Input
            label="Target ID"
            name="target-filter"
            placeholder="UUID"
            value={targetInput}
            onChange={(event) => setTargetInput(event.target.value)}
          />
          <div className="flex gap-2">
            <Button type="submit" size="sm">
              Lọc
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => {
                setActionInput("");
                setActorInput("");
                setTargetInput("");
                setFilters({});
              }}
            >
              Xóa lọc
            </Button>
          </div>
        </form>
      </Card>

      <Card className="p-0 overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-left text-xs uppercase tracking-wider text-slate-500">
            <tr>
              <th className="px-4 py-3">Thời điểm</th>
              <th className="px-4 py-3">Hành động</th>
              <th className="px-4 py-3">Kết quả</th>
              <th className="px-4 py-3">Actor</th>
              <th className="px-4 py-3">Đối tượng</th>
              <th className="px-4 py-3">Chi tiết</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {eventsQuery.isLoading && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                  Đang tải nhật ký…
                </td>
              </tr>
            )}
            {eventsQuery.isError && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-rose-600" role="alert">
                  {describeAdminError(eventsQuery.error)}
                </td>
              </tr>
            )}
            {!eventsQuery.isLoading && events.length === 0 && (
              <tr>
                <td colSpan={6} className="px-4 py-6 text-center text-slate-500">
                  Chưa có sự kiện phù hợp.
                </td>
              </tr>
            )}
            {events.map((event) => (
              <tr key={event.id} data-testid="audit-row">
                <td className="px-4 py-3 text-xs text-slate-600">
                  {new Date(event.timestamp).toLocaleString("vi-VN")}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-slate-800">{event.action}</td>
                <td className="px-4 py-3">
                  <Badge variant={event.outcome === "SUCCESS" ? "success" : "danger"}>
                    {event.outcome === "SUCCESS" ? "Thành công" : "Thất bại"}
                  </Badge>
                </td>
                <td className="px-4 py-3 font-mono text-[11px] text-slate-500">
                  {event.actorId ?? "—"}
                </td>
                <td className="px-4 py-3 font-mono text-[11px] text-slate-500">
                  {event.targetType ? `${event.targetType}:${event.targetId ?? "—"}` : "—"}
                </td>
                <td className="px-4 py-3 text-xs text-slate-600">{summary(event.metadata)}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {eventsQuery.hasNextPage && (
          <div className="p-4 border-t border-slate-100 text-center">
            <Button
              variant="outline"
              size="sm"
              isLoading={eventsQuery.isFetchingNextPage}
              onClick={() => void eventsQuery.fetchNextPage()}
            >
              Tải thêm
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}
