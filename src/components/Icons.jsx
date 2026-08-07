/* Lightweight inline SVG icon set — stroke-based, inherits currentColor. */

const base = {
  width: 18,
  height: 18,
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.9,
  strokeLinecap: "round",
  strokeLinejoin: "round",
};

export function PlaneIcon(props) {
  return (
    <svg {...base} {...props}>
      <path d="M17.8 19.2 16 11l3.5-3.5a2.1 2.1 0 0 0-3-3L13 8 4.8 6.2a.5.5 0 0 0-.5.8l3.2 4-2 2-2.2-.6a.5.5 0 0 0-.5.8L5 15.6l1.4 2.2a.5.5 0 0 0 .8-.5L6.6 15l2-2 4 3.2a.5.5 0 0 0 .8-.5Z" />
    </svg>
  );
}

export function DocIcon(props) {
  return (
    <svg {...base} {...props}>
      <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
      <path d="M14 3v5h5M9 13h6M9 17h4" />
    </svg>
  );
}

export function FuelIcon(props) {
  return (
    <svg {...base} {...props}>
      <path d="M3 21h11V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2z" />
      <path d="M6 8h5M14 9h3a2 2 0 0 1 2 2v6a1.5 1.5 0 0 0 3 0v-7l-3-3" />
    </svg>
  );
}

export function RouteIcon(props) {
  return (
    <svg {...base} {...props}>
      <circle cx="6" cy="18" r="2.5" />
      <circle cx="18" cy="6" r="2.5" />
      <path d="M8.5 18H14a3.5 3.5 0 0 0 0-7h-4a3.5 3.5 0 0 1 0-7h5.5" />
    </svg>
  );
}

export function UploadIcon(props) {
  return (
    <svg {...base} {...props}>
      <path d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5" />
      <path d="M4 15v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
    </svg>
  );
}

export function CheckIcon(props) {
  return (
    <svg {...base} strokeWidth={2.6} {...props}>
      <path d="m4.5 12.5 5 5 10-11" />
    </svg>
  );
}

export function DownloadIcon(props) {
  return (
    <svg {...base} {...props}>
      <path d="M12 4v12m0 0 4.5-4.5M12 16l-4.5-4.5" />
      <path d="M4 17v1a3 3 0 0 0 3 3h10a3 3 0 0 0 3-3v-1" />
    </svg>
  );
}

export function SparkIcon(props) {
  return (
    <svg {...base} {...props}>
      <path d="M12 3v4M12 17v4M3 12h4M17 12h4M5.6 5.6l2.8 2.8M15.6 15.6l2.8 2.8M18.4 5.6l-2.8 2.8M8.4 15.6l-2.8 2.8" />
    </svg>
  );
}
