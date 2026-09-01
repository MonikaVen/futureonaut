type IconProps = {
  className?: string;
  size?: number;
  filled?: boolean;
};

const defaults = { size: 16, className: undefined as string | undefined, filled: false };

function svgProps({ className, size }: IconProps) {
  return {
    className,
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 2,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    "aria-hidden": true,
  };
}

export function StarIcon({ className, size = defaults.size, filled = false }: IconProps) {
  return (
    <svg {...svgProps({ className, size })}>
      <polygon
        points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"
        fill={filled ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth={filled ? 0 : 2}
      />
    </svg>
  );
}

export function CommentIcon({ className, size = defaults.size }: IconProps) {
  return (
    <svg {...svgProps({ className, size })}>
      <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
    </svg>
  );
}

export function PlayIcon({ className, size = defaults.size }: IconProps) {
  return (
    <svg {...svgProps({ className, size })}>
      <polygon points="5 3 19 12 5 21 5 3" fill="currentColor" stroke="none" />
    </svg>
  );
}
