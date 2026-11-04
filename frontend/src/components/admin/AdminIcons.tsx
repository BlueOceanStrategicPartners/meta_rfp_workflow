/** SVG icons for the Admin Command Center (same style as AppNavIcons). */
import type { ReactNode } from "react";

const SIZE = 16;
const STROKE = 1.75;

function Svg({ children, size = SIZE }: { children: ReactNode; size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={STROKE}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      {children}
    </svg>
  );
}

export function IconOverview() {
  return (
    <Svg>
      <rect x="3" y="3" width="7.5" height="9" rx="1.5" />
      <rect x="13.5" y="3" width="7.5" height="5" rx="1.5" />
      <rect x="13.5" y="11" width="7.5" height="10" rx="1.5" />
      <rect x="3" y="15" width="7.5" height="6" rx="1.5" />
    </Svg>
  );
}

export function IconDebate() {
  return (
    <Svg>
      <path d="M4 5h11a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2H9l-4 3v-3H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z" />
      <path d="M19 9h1a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-1v3l-4-3h-3" />
    </Svg>
  );
}

export function IconPricing() {
  return (
    <Svg>
      <path d="M3 12V4a1 1 0 0 1 1-1h8l9 9-9 9-9-9z" />
      <circle cx="8" cy="8" r="1.5" />
    </Svg>
  );
}

export function IconNegotiation() {
  return (
    <Svg>
      <path d="M8 12l3 3 5-5" />
      <path d="M2 11l5-5 4 2 4-2 5 5-8 8z" />
    </Svg>
  );
}

export function IconInventory() {
  return (
    <Svg>
      <path d="M3 21V8l9-5 9 5v13" />
      <path d="M9 21v-6h6v6" />
      <path d="M3 21h18" />
    </Svg>
  );
}

export function IconOccupancy() {
  return (
    <Svg>
      <ellipse cx="12" cy="5" rx="8" ry="2.5" />
      <path d="M4 5v6c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5V5" />
      <path d="M4 11v6c0 1.4 3.6 2.5 8 2.5s8-1.1 8-2.5v-6" />
    </Svg>
  );
}

export function IconTelemetry() {
  return (
    <Svg>
      <path d="M3 12h4l3-7 4 14 3-7h4" />
    </Svg>
  );
}


export function IconRefresh({ size = 14 }: { size?: number }) {
  return (
    <Svg size={size}>
      <path d="M20 11a8 8 0 0 0-14.9-3.9L4 8" />
      <path d="M4 3v5h5" />
      <path d="M4 13a8 8 0 0 0 14.9 3.9L20 16" />
      <path d="M20 21v-5h-5" />
    </Svg>
  );
}

export function IconBack({ size = 14 }: { size?: number }) {
  return (
    <Svg size={size}>
      <path d="M15 18l-6-6 6-6" />
    </Svg>
  );
}

export function IconPlus({ size = 14 }: { size?: number }) {
  return (
    <Svg size={size}>
      <path d="M12 5v14M5 12h14" />
    </Svg>
  );
}

export function IconEdit({ size = 14 }: { size?: number }) {
  return (
    <Svg size={size}>
      <path d="M4 20h4L19 9l-4-4L4 16v4z" />
      <path d="M13.5 6.5l4 4" />
    </Svg>
  );
}

export function IconTrashAdmin({ size = 14 }: { size?: number }) {
  return (
    <Svg size={size}>
      <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6" />
    </Svg>
  );
}

export function IconUnlock({ size = 14 }: { size?: number }) {
  return (
    <Svg size={size}>
      <rect x="4" y="11" width="16" height="10" rx="2" />
      <path d="M8 11V7a4 4 0 0 1 7.5-2" />
    </Svg>
  );
}

export function IconUpload({ size = 18 }: { size?: number }) {
  return (
    <Svg size={size}>
      <path d="M12 16V4" />
      <path d="M7 9l5-5 5 5" />
      <path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
    </Svg>
  );
}

export function IconCopy({ size = 14 }: { size?: number }) {
  return (
    <Svg size={size}>
      <rect x="9" y="9" width="11" height="11" rx="2" />
      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
    </Svg>
  );
}

export function IconAlert({ size = 14 }: { size?: number }) {
  return (
    <Svg size={size}>
      <path d="M12 3l9.5 17h-19L12 3z" />
      <path d="M12 10v4M12 17.5v.01" />
    </Svg>
  );
}

export function IconSend({ size = 14 }: { size?: number }) {
  return (
    <Svg size={size}>
      <path d="M4 12l16-8-6 16-2.5-6.5L4 12z" />
    </Svg>
  );
}

export function IconHeadset({ size = 14 }: { size?: number }) {
  return (
    <Svg size={size}>
      <path d="M4 14v-2a8 8 0 0 1 16 0v2" />
      <rect x="3" y="14" width="4" height="6" rx="1.5" />
      <rect x="17" y="14" width="4" height="6" rx="1.5" />
    </Svg>
  );
}

export function IconClose({ size = 16 }: { size?: number }) {
  return (
    <Svg size={size}>
      <path d="M6 6l12 12M18 6L6 18" />
    </Svg>
  );
}

export function IconChevronRight({ size = 14 }: { size?: number }) {
  return (
    <Svg size={size}>
      <path d="M9 6l6 6-6 6" />
    </Svg>
  );
}
