import type { ButtonHTMLAttributes } from 'react';

type ButtonVariant = 'primary' | 'secondary' | 'ghost';
type ButtonSize = 'md' | 'lg';

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

const VARIANT_CLASS: Record<ButtonVariant, string> = {
  primary:
    'bg-brand-fill text-white hover:bg-brand-fill-strong disabled:bg-neutral-soft disabled:text-muted',
  secondary:
    'border border-line bg-surface text-ink hover:border-brand hover:text-brand disabled:text-muted',
  ghost: 'text-brand hover:bg-brand-soft disabled:text-muted',
};

const SIZE_CLASS: Record<ButtonSize, string> = {
  md: 'px-4 py-2 text-base',
  lg: 'px-5 py-3 text-lg',
};

/** 버튼 모양 클래스. 버튼처럼 보여야 하는 링크(`next/link`)도 같이 씁니다. */
export const buttonClassName = (variant: ButtonVariant = 'primary', size: ButtonSize = 'md') =>
  `focus-visible:ring-brand inline-flex items-center justify-center gap-2 rounded-xl font-semibold transition focus-visible:ring-3 focus-visible:outline-hidden disabled:cursor-not-allowed ${VARIANT_CLASS[variant]} ${SIZE_CLASS[size]}`;

export const Button = ({
  variant = 'primary',
  size = 'md',
  type = 'button',
  className = '',
  ...rest
}: ButtonProps) => (
  <button type={type} className={`${buttonClassName(variant, size)} ${className}`} {...rest} />
);
