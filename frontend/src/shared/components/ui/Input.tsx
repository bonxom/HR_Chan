import React from 'react';

interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
  leftIcon?: React.ReactNode;
}

export const Input: React.FC<InputProps> = ({
  label,
  error,
  helperText,
  leftIcon,
  className = '',
  id,
  ...props
}) => {
  const inputId = id || props.name || Math.random().toString(36).substring(7);

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={inputId} className="mb-1.5 block text-[13px] font-medium text-ink">
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
          className={`w-full rounded-control border bg-surface/90 px-3 py-2 text-sm text-ink placeholder:text-ink-subtle transition-colors focus:outline-none focus:border-brand focus:ring-3 focus:ring-brand/15 disabled:bg-canvas disabled:text-ink-subtle ${
            leftIcon ? 'pl-10' : ''
          } ${error ? 'border-danger-ink/60 focus:border-danger-ink focus:ring-danger-ink/15' : 'border-line-strong'} ${className}`}
          {...props}
        />
      </div>
      {error && <p className="mt-1.5 text-xs text-danger-ink">{error}</p>}
      {helperText && !error && <p className="mt-1.5 text-xs text-ink-subtle">{helperText}</p>}
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
  ...props
}) => {
  const inputId = id || props.name || Math.random().toString(36).substring(7);

  return (
    <div className="w-full">
      {label && (
        <label htmlFor={inputId} className="mb-1.5 block text-[13px] font-medium text-ink">
          {label}
        </label>
      )}
      <textarea
        id={inputId}
        rows={rows}
        className={`w-full rounded-control border bg-surface/90 px-3 py-2 text-sm text-ink placeholder:text-ink-subtle transition-colors focus:outline-none focus:border-brand focus:ring-3 focus:ring-brand/15 disabled:bg-canvas disabled:text-ink-subtle ${
          error ? 'border-danger-ink/60 focus:border-danger-ink focus:ring-danger-ink/15' : 'border-line-strong'
        } ${className}`}
        {...props}
      />
      {error && <p className="mt-1.5 text-xs text-danger-ink">{error}</p>}
      {helperText && !error && <p className="mt-1.5 text-xs text-ink-subtle">{helperText}</p>}
    </div>
  );
};

