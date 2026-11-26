import React, { useId } from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
  leftIcon?: React.ReactNode;
}

const LABEL_CLASS = 'mb-1.5 block text-[13px] font-medium text-ink';
const FIELD_BASE =
  'w-full rounded-control border bg-surface/90 px-3 py-2 text-sm text-ink placeholder:text-ink-subtle transition-colors focus:outline-none focus:ring-3 disabled:bg-canvas disabled:text-ink-subtle';
/** Màu viền theo trạng thái; ô lỗi vẫn đỏ khi focus, không bị màu thương hiệu ghi đè. */
function stateClasses(error?: string): string {
  return error
    ? 'border-danger-ink/60 focus:border-danger-ink focus:ring-danger-ink/15'
    : 'border-line-strong focus:border-brand focus:ring-brand/15';
}

/** Giữ aria-describedby từ nơi gọi và nối ID lỗi/gợi ý để trình đọc màn hình đọc đúng. */
function describedBy(...ids: (string | undefined | false)[]): string | undefined {
  const joined = ids.filter(Boolean).join(' ');
  return joined || undefined;
}

export const Input: React.FC<InputProps> = ({
  label,
  error,
  helperText,
  leftIcon,
  className = '',
  id,
  'aria-describedby': ariaDescribedBy,
  'aria-invalid': ariaInvalid,
  ...props
}) => {
  const generatedId = useId();
  // ID không đổi giữa các lần render để label và phần mô tả luôn trỏ đúng input.
  const inputId = id || props.name || generatedId;
  const errorId = `${inputId}-error`;
  const helperId = `${inputId}-helper`;
  const showHelper = Boolean(helperText) && !error;

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={inputId} className={LABEL_CLASS}>
          {label}
        </label>
      )}
      <div className="relative">
        {leftIcon && (
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-ink-subtle">
            {leftIcon}
          </div>
        )}
        <input
          id={inputId}
          className={`${FIELD_BASE} ${leftIcon ? 'pl-10' : ''} ${stateClasses(error)} ${className}`}
          aria-invalid={error ? true : ariaInvalid}
          aria-describedby={describedBy(ariaDescribedBy, error && errorId, showHelper && helperId)}
          {...props}
        />
      </div>
      {error && (
        <p id={errorId} className="mt-1.5 text-xs text-danger-ink">
          {error}
        </p>
      )}
      {showHelper && (
        <p id={helperId} className="mt-1.5 text-xs text-ink-subtle">
          {helperText}
        </p>
      )}
    </div>
  );
};

interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Textarea: React.FC<TextareaProps> = ({
  label,
  error,
  helperText,
  className = '',
  id,
  rows = 4,
  'aria-describedby': ariaDescribedBy,
  'aria-invalid': ariaInvalid,
  ...props
}) => {
  // Textarea dùng cùng quy tắc ID/lỗi như Input để form xử lý thống nhất.
  const generatedId = useId();
  const inputId = id || props.name || generatedId;
  const errorId = `${inputId}-error`;
  const helperId = `${inputId}-helper`;
  const showHelper = Boolean(helperText) && !error;

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={inputId} className={LABEL_CLASS}>
          {label}
        </label>
      )}
      <textarea
        id={inputId}
        rows={rows}
        className={`${FIELD_BASE} ${stateClasses(error)} ${className}`}
        aria-invalid={error ? true : ariaInvalid}
        aria-describedby={describedBy(ariaDescribedBy, error && errorId, showHelper && helperId)}
        {...props}
      />
      {error && (
        <p id={errorId} className="mt-1.5 text-xs text-danger-ink">
          {error}
        </p>
      )}
      {showHelper && (
        <p id={helperId} className="mt-1.5 text-xs text-ink-subtle">
          {helperText}
        </p>
      )}
    </div>
  );
};
