import React from 'react';

interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'danger' | 'ghost' | 'success';
  size?: 'sm' | 'md' | 'lg';
  isLoading?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
}

export const Button: React.FC<ButtonProps> = ({
  children,
  variant = 'primary',
  size = 'md',
  isLoading = false,
  leftIcon,
  rightIcon,
  className = '',
  disabled,
  ...props
}) => {
  const baseStyles =
    'inline-flex items-center justify-center font-medium rounded-control transition-colors select-none cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-offset-canvas disabled:opacity-50 disabled:cursor-not-allowed';

  const sizeStyles = {
    sm: 'h-8 text-[13px] px-3 gap-1.5',
    md: 'h-9 text-sm px-3.5 gap-2',
    lg: 'h-11 text-[15px] px-5 gap-2',
  };

  const variantStyles = {
    primary: 'bg-brand text-white hover:bg-brand-hover shadow-[inset_0_1px_0_rgba(255,255,255,0.18)] focus-visible:ring-brand',
    secondary: 'bg-ink text-white hover:bg-ink/85 focus-visible:ring-ink',
    outline: 'border border-line-strong bg-surface/80 text-ink hover:bg-surface focus-visible:ring-brand',
    danger: 'bg-danger-ink text-white hover:bg-danger-ink/90 focus-visible:ring-danger-ink',
    ghost: 'text-ink-muted hover:bg-ink/5 hover:text-ink focus-visible:ring-brand',
    success: 'bg-brand-soft text-brand-ink hover:bg-brand-soft/70 ring-1 ring-inset ring-brand/20 focus-visible:ring-brand',
  };

  return (
    <button
      className={`${baseStyles} ${sizeStyles[size]} ${variantStyles[variant]} ${className}`}
      disabled={disabled || isLoading}
      {...props}
    >
      {isLoading ? (
        <svg className="animate-spin h-4 w-4 text-current" fill="none" viewBox="0 0 24 24" aria-hidden="true">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path
            className="opacity-75"
            fill="currentColor"
            d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
          />
        </svg>
      ) : (
        leftIcon
      )}
      <span>{children}</span>
      {!isLoading && rightIcon}
    </button>
  );
};
