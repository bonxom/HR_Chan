import React, { useState, useEffect } from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';
import { GLASS_LAYER } from './Glass';

export interface ToastMessage {
  id: string;
  type: 'success' | 'error' | 'info';
  title?: string;
  message: string;
}

let addToastHandler: ((toast: Omit<ToastMessage, 'id'>) => void) | null = null;

export const showToast = (toast: Omit<ToastMessage, 'id'>) => {
  if (addToastHandler) {
    addToastHandler(toast);
  }
};

export const ToastContainer: React.FC = () => {
  const [toasts, setToasts] = useState<ToastMessage[]>([]);

  useEffect(() => {
    addToastHandler = (newToast) => {
      const id = Math.random().toString(36).substring(7);
      setToasts((prev) => [...prev, { ...newToast, id }]);

      setTimeout(() => {
        setToasts((prev) => prev.filter((t) => t.id !== id));
      }, 4000);
    };

    return () => {
      addToastHandler = null;
    };
  }, []);

  const removeToast = (id: string) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  if (toasts.length === 0) return null;

  return (
    <div className="pointer-events-none fixed bottom-5 right-5 z-[80] flex w-full max-w-sm flex-col gap-2.5" aria-live="polite">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`pointer-events-auto flex items-start gap-3 rounded-2xl p-4 text-ink ${GLASS_LAYER}`}
        >
          {toast.type === 'success' && <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-brand" />}
          {toast.type === 'error' && <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-danger-ink" />}
          {toast.type === 'info' && <Info className="mt-0.5 h-5 w-5 shrink-0 text-info-ink" />}

          <div className="flex-1 text-[13px]">
            {toast.title && <div className="mb-0.5 text-sm font-semibold">{toast.title}</div>}
            <div className="leading-relaxed text-ink-muted">{toast.message}</div>
          </div>

          <button
            type="button"
            onClick={() => removeToast(toast.id)}
            aria-label="Đóng thông báo"
            className="cursor-pointer rounded p-0.5 text-ink-subtle hover:text-ink"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ))}
    </div>
  );
};
