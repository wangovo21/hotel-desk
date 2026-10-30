/** 极简线性图标（24×24，currentColor）。不引图标库：9 个图标不值得多一个依赖。 */
type P = { size?: number };

const base = (size = 18) => ({
  width: size,
  height: size,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.7,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
});

export function IconDesk({ size }: P) {
  return (
    <svg {...base(size)}>
      <path d="M3 20h18" />
      <path d="M5 20V9l7-4 7 4v11" />
      <path d="M9 20v-5h6v5" />
    </svg>
  );
}

export function IconCheckin({ size }: P) {
  return (
    <svg {...base(size)}>
      <rect x="3" y="5" width="18" height="16" rx="2" />
      <path d="M8 3v4M16 3v4M3 11h18" />
      <path d="M9 16h6M12 13v6" />
    </svg>
  );
}

export function IconBed({ size }: P) {
  return (
    <svg {...base(size)}>
      <path d="M3 18v-7h18v7" />
      <path d="M3 18h18" />
      <path d="M6 11V8h5v3M13 11V8h5v3" />
      <path d="M3 11V6" />
    </svg>
  );
}

export function IconRecords({ size }: P) {
  return (
    <svg {...base(size)}>
      <path d="M6 3h9l4 4v14H6z" />
      <path d="M15 3v4h4" />
      <path d="M9 12h7M9 16h5" />
    </svg>
  );
}

export function IconGuest({ size }: P) {
  return (
    <svg {...base(size)}>
      <circle cx="12" cy="8" r="3.4" />
      <path d="M4.5 20c.9-3.6 3.9-5.6 7.5-5.6s6.6 2 7.5 5.6" />
    </svg>
  );
}

export function IconChart({ size }: P) {
  return (
    <svg {...base(size)}>
      <path d="M4 20V4" />
      <path d="M4 20h16" />
      <path d="M8 16v-4M12.5 16V8M17 16v-6" />
    </svg>
  );
}

export function IconDoor({ size }: P) {
  return (
    <svg {...base(size)}>
      <rect x="5" y="3" width="14" height="18" rx="1.5" />
      <circle cx="15" cy="12" r="1" />
      <path d="M9 3v18" />
    </svg>
  );
}

export function IconLayers({ size }: P) {
  return (
    <svg {...base(size)}>
      <path d="M12 3l8 4-8 4-8-4 8-4z" />
      <path d="M4 12l8 4 8-4" />
      <path d="M4 17l8 4 8-4" />
    </svg>
  );
}

export function IconGear({ size }: P) {
  return (
    <svg {...base(size)}>
      <circle cx="12" cy="12" r="3" />
      <path d="M12 3v2.2M12 18.8V21M4.2 7.5l1.9 1.1M17.9 15.4l1.9 1.1M19.8 7.5l-1.9 1.1M6.1 15.4l-1.9 1.1" />
    </svg>
  );
}

export function IconSearch({ size }: P) {
  return (
    <svg {...base(size)}>
      <circle cx="11" cy="11" r="6" />
      <path d="M16 16l4 4" />
    </svg>
  );
}
