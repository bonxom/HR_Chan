import React, { useState, useEffect } from 'react';
import { CheckCircle2, AlertCircle, Info, X } from 'lucide-react';

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
    <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2.5 max-w-sm w-full pointer-events-none">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          className={`pointer-events-auto flex items-start gap-3 p-4 rounded-xl shadow-lg border backdrop-blur-md transition-all animate-in slide-in-from-bottom-5 ${
            toast.type === 'success'
              ? 'bg-emerald-50/95 border-emerald-200 text-emerald-900'
              : toast.type === 'error'
              ? 'bg-rose-50/95 border-rose-200 text-rose-900'
              : 'bg-slate-900/95 border-slate-800 text-white'
          }`}
        >
          {toast.type === 'success' && <CheckCircle2 className="w-5 h-5 text-emerald-600 shrink-0 mt-0.5" />}
          {toast.type === 'error' && <AlertCircle className="w-5 h-5 text-rose-600 shrink-0 mt-0.5" />}
          {toast.type === 'info' && <Info className="w-5 h-5 text-sky-400 shrink-0 mt-0.5" />}

          <div className="flex-1 text-xs">
            {toast.title && <div className="font-bold text-sm mb-0.5">{toast.title}</div>}
            <div className="leading-relaxed">{toast.message}</div>
          </div>

          <button
            onClick={() => removeToast(toast.id)}
            className="text-current opacity-50 hover:opacity-100 p-0.5 rounded cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ))}
    </div>
  );
};

