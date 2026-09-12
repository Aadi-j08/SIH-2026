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

export const LogOut = (p: IconProps) => (
  <Icon {...p} strokeWidth={2.25}>
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
  </Icon>
);
export const LogIn = (p: IconProps) => (
  <Icon {...p} strokeWidth={2.25}>
    <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4M10 17l5-5-5-5M15 12H3" />
  </Icon>
);
export const Eye = (p: IconProps) => (
  <Icon {...p}>
    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
    <circle cx="12" cy="12" r="3" />
  </Icon>
);
export const EyeOff = (p: IconProps) => (
  <Icon {...p}>
    <path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-11-8-11-8a20.3 20.3 0 0 1 5.06-5.94M9.9 4.24A10.94 10.94 0 0 1 12 4c7 0 11 8 11 8a20.3 20.3 0 0 1-4.13 5.19M14.12 14.12a3 3 0 1 1-4.24-4.24M1 1l22 22" />
  </Icon>
);
export const Lock = (p: IconProps) => (
  <Icon {...p}>
    <rect x="3" y="11" width="18" height="11" rx="2" />
    <path d="M7 11V7a5 5 0 0 1 10 0v4" />
  </Icon>
);
export const Shield = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
  </Icon>
);
export const Info = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="10" />
    <path d="M12 16v-4M12 8h.01" />
  </Icon>
);
export const Home = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3 11l9-8 9 8M5 10v10h14V10M10 20v-6h4v6" />
  </Icon>
);
export const ChevronDown = (p: IconProps) => (
  <Icon {...p} strokeWidth={2.25}>
    <path d="M6 9l6 6 6-6" />
  </Icon>
);
export const Bill = (p: IconProps) => (
  <Icon {...p}>
    <path d="M4 2v20l2-1 2 1 2-1 2 1 2-1 2 1 2-1 2 1V2l-2 1-2-1-2 1-2-1-2 1-2-1-2 1z" />
    <path d="M8 8h8M8 12h8M8 16h5" />
  </Icon>
);

export const Bell = (p: IconProps) => (
  <Icon {...p}>
    <path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9M13.7 21a2 2 0 0 1-3.4 0" />
  </Icon>
);
export const Settings = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z" />
  </Icon>
);
export const Coins = (p: IconProps) => (
  <Icon {...p}>
    <ellipse cx="9" cy="6" rx="6" ry="3" />
    <path d="M3 6v6c0 1.7 2.7 3 6 3s6-1.3 6-3V6M3 12v6c0 1.7 2.7 3 6 3s6-1.3 6-3v-6" />
    <path d="M15 9.5c3.3 0 6 1.3 6 3v6c0 1.7-2.7 3-6 3" />
  </Icon>
);
export const Scale = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 3v18M5 21h14M3 7h18M6 7l-3 7a3 3 0 0 0 6 0L6 7zM18 7l-3 7a3 3 0 0 0 6 0l-3-7z" />
  </Icon>
);
export const Megaphone = (p: IconProps) => (
  <Icon {...p}>
    <path d="M3 11v2a2 2 0 0 0 2 2h2l5 4V5L7 9H5a2 2 0 0 0-2 2zM16 8.5a4 4 0 0 1 0 7M8 15l1 5h2" />
  </Icon>
);
export const Building = (p: IconProps) => (
  <Icon {...p}>
    <rect x="4" y="3" width="16" height="18" rx="1.5" />
    <path d="M9 21v-4h6v4M8 7h2M14 7h2M8 11h2M14 11h2M8 15h2M14 15h2" />
  </Icon>
);
export const ShieldCheck = (p: IconProps) => (
  <Icon {...p} strokeWidth={2.25}>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    <path d="M9 12l2 2 4-4" />
  </Icon>
);
export const AlertCircle = (p: IconProps) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="10" />
    <path d="M12 8v4M12 16h.01" />
  </Icon>
);
export const Sparkle = (p: IconProps) => (
  <Icon {...p}>
    <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8L12 3zM19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8L19 16z" />
  </Icon>
);
export const MapPin = (p: IconProps) => (
  <Icon {...p}>
    <path d="M21 10c0 7-9 13-9 13S3 17 3 10a9 9 0 0 1 18 0z" />
    <circle cx="12" cy="10" r="3" />
  </Icon>
);

export const TRADE_ICONS: Record<string, (p: IconProps) => ReactElement> = {
  plumbing: Wrench,
  electrical: Zap,
  carpentry: Hammer,
  cleaning: Sparkles,
  painting: Roller,
};
