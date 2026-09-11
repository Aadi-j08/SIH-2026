import type { ReactElement, SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number };

function Icon({ size = 24, children, ...rest }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...rest}
    >
      {children}
    </svg>
  );
}

export const Wrench = (p: IconProps) => (
  <Icon {...p}>
    <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
  </Icon>
);
export const Zap = (p: IconProps) => (
  <Icon {...p}>
    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
  </Icon>
);
export const Hammer = (p: IconProps) => (
  <Icon {...p}>
    <path d="M15 12 6.5 20.5a2.12 2.12 0 0 1-3-3L12 9" />
    <path d="M17.64 15 22 10.64" />
    <path d="m20.91 11.7-1.25-1.25c-.6-.6-.93-1.4-.93-2.25v-.86L16.01 4.6A5.56 5.56 0 0 0 12.07 3H9l.92.82A6.18 6.18 0 0 1 12 8.4v1.56l2 2h2.47l2.26 1.91" />
  </Icon>
);
export const Sparkles = (p: IconProps) => (
  <Icon {...p}>
    <path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3L12 3z" />
  </Icon>
);
export const Roller = (p: IconProps) => (
  <Icon {...p}>
    <rect x="3" y="4" width="14" height="6" rx="1.5" />
    <path d="M17 7h3v5h-8v2" />
    <rect x="10" y="14" width="4" height="7" rx="1" />
  </Icon>
);
export const Pin = (p: IconProps) => (
  <Icon {...p}>
    <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0z" />
    <circle cx="12" cy="10" r="3" />
  </Icon>
);
export const Locate = (p: IconProps) => (
  <Icon {...p} strokeWidth={2}>
    <circle cx="12" cy="12" r="7" />
    <path d="M12 2v3M12 19v3M2 12h3M19 12h3" />
  </Icon>
);
export const Clock = (p: IconProps) => (
  <Icon {...p} strokeWidth={2}>
    <circle cx="12" cy="12" r="9" />
    <path d="M12 7v5l3 2" />
  </Icon>
);
export const ArrowRight = (p: IconProps) => (
  <Icon {...p} strokeWidth={2.25}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </Icon>
);
export const Mic = (p: IconProps) => (
  <Icon {...p} strokeWidth={2}>
    <rect x="9" y="3" width="6" height="11" rx="3" />
    <path d="M5 11a7 7 0 0 0 14 0M12 18v3M9 21h6" />
  </Icon>
);
export const Check = (p: IconProps) => (
  <Icon {...p} strokeWidth={2.5}>
    <path d="M5 12l4 4L19 6" />
  </Icon>
);
export const Cross = (p: IconProps) => (
  <Icon {...p} strokeWidth={2.5}>
    <path d="M6 6l12 12M18 6L6 18" />
  </Icon>
);
export const Waveform = (p: IconProps) => (
  <Icon {...p} strokeWidth={2}>
    <path d="M4 9v6M8 5v14M12 8v8M16 3v18M20 9v6" />
  </Icon>
);
export const Star = (p: IconProps & { filled?: boolean }) => {
  const { filled, ...rest } = p;
  return (
    <Icon {...rest} fill={filled ? "currentColor" : "none"} strokeWidth={1.75}>
      <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
    </Icon>
  );
};
export const Plus = (p: IconProps) => (
  <Icon {...p} strokeWidth={2}>
    <path d="M12 5v14M5 12h14" />
  </Icon>
);
export const Refresh = (p: IconProps) => (
  <Icon {...p} strokeWidth={2}>
    <path d="M21 12a9 9 0 1 1-2.64-6.36" />
    <path d="M21 3v6h-6" />
  </Icon>
);

export const ArrowLeft = (p: IconProps) => (
  <Icon {...p} strokeWidth={2.25}>
    <path d="M19 12H5M11 6l-6 6 6 6" />
  </Icon>
);
export const ArrowDown = (p: IconProps) => (
  <Icon {...p} strokeWidth={2.25}>
    <path d="M12 5v14M6 13l6 6 6-6" />
  </Icon>
);
export const ListOrdered = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3 6h18M3 12h12M3 18h6" />
  </Icon>
);
export const Receipt = (p: IconProps) => (
  <Icon {...p}>
    <path d="M5 3h14v18l-2.5-1.5L14 21l-2-1.5L10 21l-2.5-1.5L5 21z" />
    <path d="M9 8h6M9 12h6M9 16h4" />
  </Icon>
);
export const TrendingUp = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3 17l6-6 4 4 8-8" />
    <path d="M15 7h6v6" />
  </Icon>
);
export const LayoutGrid = (p: IconProps) => (
  <Icon {...p}>
    <rect x="3" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="3" width="7" height="7" rx="1.5" />
    <rect x="3" y="14" width="7" height="7" rx="1.5" />
    <rect x="14" y="14" width="7" height="7" rx="1.5" />
  </Icon>
);
export const CalendarIcon = (p: IconProps) => (
  <Icon {...p}>
    <rect x="3" y="5" width="18" height="16" rx="2" />
    <path d="M3 10h18M8 3v4M16 3v4" />
  </Icon>
);
export const Users = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="9" cy="8" r="3.5" />
    <path d="M2.5 20a6.5 6.5 0 0 1 13 0" />
    <path d="M16 4.5a3.5 3.5 0 0 1 0 7M21.5 20a6.5 6.5 0 0 0-4.5-6.2" />
  </Icon>
);

export const TRADE_ICONS: Record<string, (p: IconProps) => ReactElement> = {
  plumbing: Wrench,
  electrical: Zap,
  carpentry: Hammer,
  cleaning: Sparkles,
  painting: Roller,
};
