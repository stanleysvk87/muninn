// Inlined from ~/midgard/brand/svg/midgardnet-mark-mono.svg (uses currentColor,
// so it must be inline SVG, not <img src>, to inherit the surrounding text color).
export default function Logo({ size = 28, className = "", style = {} }) {
  return (
    <svg viewBox="0 0 32 32" width={size} height={size} className={className} style={style} aria-hidden="true">
      <g fill="none" stroke="currentColor" strokeWidth="1.0" strokeLinecap="round" opacity="0.26">
        <line x1="3" y1="25.5" x2="16" y2="20" />
        <line x1="29" y1="25.5" x2="16" y2="20" />
      </g>
      <polyline
        points="3,25.5 9.5,6.5 16,20 22.5,6.5 29,25.5"
        fill="none"
        stroke="currentColor"
        strokeWidth="2.8"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx="3" cy="25.5" r="1.9" fill="currentColor" />
      <circle cx="9.5" cy="6.5" r="1.9" fill="currentColor" />
      <circle cx="16" cy="20" r="2.7" fill="currentColor" />
      <circle cx="22.5" cy="6.5" r="1.9" fill="currentColor" />
      <circle cx="29" cy="25.5" r="1.9" fill="currentColor" />
    </svg>
  );
}
