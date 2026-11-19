import { focusErrorTarget } from "./useErrorFocus";
import type { ErrorSummaryItem } from "./validation";

interface FormErrorSummaryProps {
  id: string;
  items: ErrorSummaryItem[];
  /** Error not tied to a field (business rule, conflict, network, unmapped 422). */
  message: string | null;
}

/** Top-of-form alert listing every field error; each entry moves focus to its field. */
export function FormErrorSummary({ id, items, message }: FormErrorSummaryProps) {
  // Mỗi mục chỉ lưu ID đích, dùng chung cơ chế focus với form để click lỗi tới đúng ô.
  if (items.length === 0 && !message) return null;
  return (
    <div
      id={id}
      role="alert"
      tabIndex={-1}
      className="p-3 text-xs text-rose-700 bg-rose-50 border border-rose-200 rounded-lg space-y-1.5 focus:outline-none focus:ring-2 focus:ring-rose-300"
    >
      {message && <p>{message}</p>}
      {items.length > 0 && (
        <>
          <p className="font-semibold">Vui lòng kiểm tra lại {items.length} mục sau:</p>
          <ul className="list-disc pl-5 space-y-0.5">
            {items.map((item) => (
              <li key={item.key}>
                <button
                  type="button"
                  onClick={() => focusErrorTarget(item.targetId)}
                  className="text-left hover:underline cursor-pointer"
                >
                  {item.message}
                </button>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
