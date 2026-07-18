"use client";

import { cn } from "@/lib/utils";
import { Check, ChevronDown } from "lucide-react";
import { createPortal } from "react-dom";
import {
  forwardRef,
  useEffect,
  useId,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type KeyboardEvent,
  type ReactNode,
  type CSSProperties,
} from "react";

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps
  extends Omit<
    ButtonHTMLAttributes<HTMLButtonElement>,
    "defaultValue" | "onChange" | "value"
  > {
  label?: string;
  error?: string;
  options: SelectOption[];
  placeholder?: string;
  value?: string;
  defaultValue?: string;
  onValueChange?: (value: string) => void;
  name?: string;
  required?: boolean;
  leadingIcon?: ReactNode;
  compact?: boolean;
  containerClassName?: string;
  menuClassName?: string;
  displayValue?: string;
}

const Select = forwardRef<HTMLButtonElement, SelectProps>(
  (
    {
      className,
      containerClassName,
      menuClassName,
      label,
      error,
      options,
      placeholder,
      value,
      defaultValue = "",
      onValueChange,
      name,
      required,
      id,
      disabled,
      leadingIcon,
      compact = false,
      displayValue,
      "aria-label": ariaLabel,
      ...props
    },
    forwardedRef
  ) => {
    const generatedId = useId();
    const selectId = id || `${generatedId}-select`;
    const listboxId = `${selectId}-listbox`;
    const labelId = label ? `${selectId}-label` : undefined;
    const errorId = error ? `${selectId}-error` : undefined;
    const wrapperRef = useRef<HTMLDivElement>(null);
    const triggerRef = useRef<HTMLButtonElement | null>(null);
    const listboxRef = useRef<HTMLDivElement>(null);
    const optionRefs = useRef<Array<HTMLButtonElement | null>>([]);
    const [open, setOpen] = useState(false);
    const [uncontrolledValue, setUncontrolledValue] = useState(defaultValue);
    const [menuPosition, setMenuPosition] = useState<CSSProperties | null>(null);
    const selectedValue = value ?? uncontrolledValue;
    const selectedIndex = options.findIndex((option) => option.value === selectedValue);
    const [activeIndex, setActiveIndex] = useState(Math.max(selectedIndex, 0));

    const selectedOption = useMemo(
      () => options.find((option) => option.value === selectedValue),
      [options, selectedValue]
    );

    const setTriggerRef = (node: HTMLButtonElement | null) => {
      triggerRef.current = node;
      if (typeof forwardedRef === "function") forwardedRef(node);
      else if (forwardedRef) forwardedRef.current = node;
    };

    const closeAndFocus = () => {
      setOpen(false);
      requestAnimationFrame(() => triggerRef.current?.focus());
    };

    const choose = (nextValue: string) => {
      if (value === undefined) setUncontrolledValue(nextValue);
      onValueChange?.(nextValue);
      closeAndFocus();
    };

    const openAt = (index: number) => {
      setActiveIndex(Math.max(0, Math.min(index, options.length - 1)));
      setOpen(true);
    };

    useEffect(() => {
      if (!open) return;
      const onPointerDown = (event: PointerEvent) => {
        const target = event.target as Node;
        if (
          !wrapperRef.current?.contains(target) &&
          !listboxRef.current?.contains(target)
        ) {
          setOpen(false);
        }
      };
      document.addEventListener("pointerdown", onPointerDown);
      return () => document.removeEventListener("pointerdown", onPointerDown);
    }, [open]);

    useLayoutEffect(() => {
      if (!open) return;

      const positionMenu = () => {
        const trigger = triggerRef.current;
        if (!trigger) return;
        const rect = trigger.getBoundingClientRect();
        const desiredWidth = Math.max(rect.width, compact ? 190 : rect.width);
        const left = Math.max(
          12,
          Math.min(rect.left, window.innerWidth - desiredWidth - 12)
        );
        const spaceBelow = window.innerHeight - rect.bottom - 12;
        const spaceAbove = rect.top - 12;
        const openUpward = spaceBelow < 220 && spaceAbove > spaceBelow;
        const availableSpace = openUpward ? spaceAbove : spaceBelow;
        setMenuPosition({
          left,
          width: desiredWidth,
          maxHeight: Math.max(140, Math.min(320, availableSpace - 8)),
          ...(openUpward
            ? { bottom: window.innerHeight - rect.top + 8 }
            : { top: rect.bottom + 8 }),
        });
      };

      positionMenu();
      window.addEventListener("resize", positionMenu);
      window.addEventListener("scroll", positionMenu, true);
      return () => {
        window.removeEventListener("resize", positionMenu);
        window.removeEventListener("scroll", positionMenu, true);
      };
    }, [compact, open]);

    useEffect(() => {
      if (!open) return;
      requestAnimationFrame(() => optionRefs.current[activeIndex]?.focus());
    }, [activeIndex, open]);

    const handleTriggerKeyDown = (event: KeyboardEvent<HTMLButtonElement>) => {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        openAt(selectedIndex >= 0 ? selectedIndex : 0);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        openAt(selectedIndex >= 0 ? selectedIndex : options.length - 1);
      } else if (event.key === "Home") {
        event.preventDefault();
        openAt(0);
      } else if (event.key === "End") {
        event.preventDefault();
        openAt(options.length - 1);
      } else if (event.key === "Escape" && open) {
        event.preventDefault();
        closeAndFocus();
      }
    };

    const handleOptionKeyDown = (
      event: KeyboardEvent<HTMLButtonElement>,
      optionIndex: number
    ) => {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setActiveIndex((current) => (current + 1) % options.length);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        setActiveIndex((current) => (current - 1 + options.length) % options.length);
      } else if (event.key === "Home") {
        event.preventDefault();
        setActiveIndex(0);
      } else if (event.key === "End") {
        event.preventDefault();
        setActiveIndex(options.length - 1);
      } else if (event.key === "Escape") {
        event.preventDefault();
        closeAndFocus();
      } else if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        choose(options[optionIndex].value);
      } else if (event.key === "Tab") {
        setOpen(false);
      }
    };

    return (
      <div ref={wrapperRef} className={cn("relative w-full", containerClassName)}>
        {label && (
          <label
            id={labelId}
            htmlFor={selectId}
            className="mb-2 block text-xs font-medium uppercase tracking-wide text-text-secondary"
          >
            {label}
          </label>
        )}
        <button
          ref={setTriggerRef}
          id={selectId}
          type="button"
          role="combobox"
          aria-controls={listboxId}
          aria-expanded={open}
          aria-haspopup="listbox"
          aria-label={ariaLabel}
          aria-labelledby={ariaLabel ? undefined : labelId}
          aria-describedby={errorId}
          aria-invalid={Boolean(error)}
          aria-required={required}
          disabled={disabled}
          onClick={() => (open ? closeAndFocus() : openAt(selectedIndex >= 0 ? selectedIndex : 0))}
          onKeyDown={handleTriggerKeyDown}
          className={cn(
            "flex w-full items-center gap-2 rounded-xl border border-border-subtle bg-bg-tertiary text-left text-sm text-text-primary outline-none",
            "transition-[border-color,background-color,box-shadow] duration-150 hover:border-border-default hover:bg-bg-elevated",
            "focus-visible:border-accent/60 focus-visible:ring-2 focus-visible:ring-accent/20",
            "disabled:cursor-not-allowed disabled:opacity-50",
            compact ? "h-10 px-3" : "h-11 px-4",
            open && "border-accent/50 bg-bg-elevated ring-2 ring-accent/15",
            error && "border-danger focus-visible:border-danger focus-visible:ring-danger/20",
            className
          )}
          {...props}
        >
          {leadingIcon && <span className="shrink-0 text-text-muted">{leadingIcon}</span>}
          <span
            className={cn(
              "min-w-0 flex-1 truncate",
              !selectedOption && !displayValue && "text-text-muted"
            )}
          >
            {displayValue || selectedOption?.label || placeholder || "Select an option"}
          </span>
          <ChevronDown
            aria-hidden
            className={cn(
              "h-4 w-4 shrink-0 text-text-muted transition-transform duration-150",
              open && "rotate-180 text-text-secondary"
            )}
          />
        </button>

        {name && <input type="hidden" name={name} value={selectedValue} />}

        {open && menuPosition &&
          createPortal(
            <div
              ref={listboxRef}
              id={listboxId}
              role="listbox"
              aria-label={ariaLabel || label || placeholder || "Options"}
              style={menuPosition}
              className={cn(
                "fixed z-[100] overflow-y-auto rounded-xl border border-border-default bg-bg-elevated p-1.5 shadow-2xl shadow-black/50",
                menuClassName
              )}
            >
              {options.map((option, index) => {
                const selected = option.value === selectedValue;
                return (
                  <button
                    key={option.value}
                    ref={(node) => {
                      optionRefs.current[index] = node;
                    }}
                    type="button"
                    role="option"
                    aria-selected={selected}
                    tabIndex={index === activeIndex ? 0 : -1}
                    onFocus={() => setActiveIndex(index)}
                    onPointerMove={() => setActiveIndex(index)}
                    onClick={() => choose(option.value)}
                    onKeyDown={(event) => handleOptionKeyDown(event, index)}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm text-text-secondary outline-none transition-colors",
                      "hover:bg-white/[0.06] focus-visible:bg-white/[0.07] focus-visible:text-text-primary",
                      selected && "bg-accent/12 text-text-primary"
                    )}
                  >
                    <span className="min-w-0 flex-1 truncate">{option.label}</span>
                    <Check
                      aria-hidden
                      className={cn(
                        "h-4 w-4 shrink-0 text-accent",
                        selected ? "opacity-100" : "opacity-0"
                      )}
                    />
                  </button>
                );
              })}
            </div>,
            document.body
          )}

        {error && (
          <p id={errorId} className="mt-1.5 text-xs text-danger">
            {error}
          </p>
        )}
      </div>
    );
  }
);

Select.displayName = "Select";

export { Select };
