const NAV_ICON_SIZE = 15;
const NAV_ICON_STROKE = 1.75;

export function IconNavClient() {
  return (
    <svg
      width={NAV_ICON_SIZE}
      height={NAV_ICON_SIZE}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={NAV_ICON_STROKE}
      aria-hidden
    >
      <circle cx="12" cy="8" r="3.5" />
      <path d="M6 20c0-3.3 2.7-6 6-6s6 2.7 6 6" />
    </svg>
  );
}

export function IconNavDesigner() {
  return (
    <svg
      width={NAV_ICON_SIZE}
      height={NAV_ICON_SIZE}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={NAV_ICON_STROKE}
      aria-hidden
    >
      <path d="M12 3l1.5 4.5L18 9l-4.5 1.5L12 15l-1.5-4.5L6 9l4.5-1.5L12 3z" />
      <path d="M5 19h14" />
    </svg>
  );
}

export function IconNavMap() {
  return (
    <svg
      width={NAV_ICON_SIZE}
      height={NAV_ICON_SIZE}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={NAV_ICON_STROKE}
      aria-hidden
    >
      <path d="M9 4l-5 2v14l5-2 6 2 5-2V4l-5 2-6-2z" />
      <path d="M9 4v14M15 6v14" />
    </svg>
  );
}

export function IconNavAdmin() {
  return (
    <svg
      width={NAV_ICON_SIZE}
      height={NAV_ICON_SIZE}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={NAV_ICON_STROKE}
      aria-hidden
    >
      <path d="M12 3l7 4v6c0 4-3 7-7 8-4-1-7-4-7-8V7l7-4z" />
      <path d="M9.5 12.5l1.8 1.8 3.5-3.8" />
    </svg>
  );
}
