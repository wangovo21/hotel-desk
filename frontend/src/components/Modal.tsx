import { useEffect, type ReactNode } from "react";

interface ModalProps {
  open: boolean;
  title: string;
  subtitle?: ReactNode;
  onClose: () => void;
  children: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg";
}

/**
 * 弹窗。三个细节是刻意做的：
 *   · ESC 关闭 —— 前台戴着工牌单手操作，找叉号太慢；
 *   · 点遮罩关闭 —— 这是常见预期，但**表单没提交时不拦**，因为拦了也没用，
 *     用户会以为按钮坏了；
 *   · 打开时锁 body 滚动 —— 否则滚轮会滚到底下的房态看板，看着像页面乱了。
 */
export function Modal({ open, title, subtitle, onClose, children, footer, size = "md" }: ModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = previous;
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="hd-modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div className={`hd-modal hd-modal--${size}`} role="dialog" aria-modal="true" aria-label={title}>
        <div className="hd-modal__head">
          <div>
            <h2 className="hd-modal__title">{title}</h2>
            {subtitle && <div className="hd-modal__subtitle">{subtitle}</div>}
          </div>
          <button className="hd-modal__close" onClick={onClose} aria-label="关闭">
            ×
          </button>
        </div>
        <div className="hd-modal__body">{children}</div>
        {footer && <div className="hd-modal__foot">{footer}</div>}
      </div>
    </div>
  );
}
