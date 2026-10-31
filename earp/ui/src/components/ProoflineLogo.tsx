import React from 'react';

interface ProoflineLogoProps {
  size?: number;
  showText?: boolean;
  showBadge?: boolean;
  version?: string;
  className?: string;
}

export const ProoflineLogo: React.FC<ProoflineLogoProps> = ({
  size = 32,
  showText = true,
  showBadge = true,
  version = 'v1.2.0',
  className = '',
}) => {
  return (
    <div
      className={`proofline-logo-container ${className}`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '10px',
        userSelect: 'none',
        textDecoration: 'none',
      }}
    >
      {/* Bespoke Geometric Shield & Invariant Laser Mark */}
      <div
        style={{
          width: size,
          height: size,
          position: 'relative',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          flexShrink: 0,
        }}
      >
        <svg
          width={size}
          height={size}
          viewBox="0 0 36 36"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          style={{
            filter: 'drop-shadow(0 2px 8px rgba(0, 234, 100, 0.25))',
            transition: 'transform 0.25s cubic-bezier(0.16, 1, 0.3, 1)',
          }}
          className="proofline-logo-svg"
        >
          <defs>
            <linearGradient id="shieldGrad" x1="0" y1="0" x2="36" y2="36" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#1e293b" />
              <stop offset="100%" stopColor="#0a0e17" />
            </linearGradient>
            <linearGradient id="laserGrad" x1="6" y1="6" x2="30" y2="30" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#10b981" />
              <stop offset="50%" stopColor="#059669" />
              <stop offset="100%" stopColor="#38bdf8" />
            </linearGradient>
            <linearGradient id="strokeGrad" x1="0" y1="0" x2="36" y2="36" gradientUnits="userSpaceOnUse">
              <stop offset="0%" stopColor="#2e3c54" />
              <stop offset="50%" stopColor="#10b981" stopOpacity="0.8" />
              <stop offset="100%" stopColor="#1e293b" />
            </linearGradient>
          </defs>

          {/* Outer Shield Container */}
          <path
            d="M18 3L30 8V18C30 25.5 24.5 31.5 18 33.5C11.5 31.5 6 25.5 6 18V8L18 3Z"
            fill="url(#shieldGrad)"
            stroke="url(#strokeGrad)"
            strokeWidth="1.5"
            strokeLinejoin="round"
          />

          {/* Inner Invariant Horizon Grid Line */}
          <path
            d="M10 18H26"
            stroke="#1e293b"
            strokeWidth="1.2"
            strokeDasharray="2 2"
          />

          {/* Invariant Verification Check & Laser Horizon */}
          <path
            d="M12 18.5L16 22.5L24 13.5"
            stroke="url(#laserGrad)"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />

          {/* Anchor Node Dot */}
          <circle cx="18" cy="7" r="1.5" fill="#10b981" />
        </svg>
      </div>

      {/* Brand Typography */}
      {showText && (
        <div style={{ display: 'flex', alignItems: 'baseline', gap: '8px' }}>
          <span
            style={{
              fontSize: size >= 32 ? '1.15rem' : '0.98rem',
              fontWeight: 800,
              color: '#ffffff',
              letterSpacing: '-0.03em',
              lineHeight: 1,
            }}
          >
            Proofline
          </span>
          {showBadge && (
            <span
              style={{
                fontSize: '0.62rem',
                fontFamily: 'var(--font-mono)',
                color: '#10b981',
                background: 'rgba(16, 185, 129, 0.08)',
                border: '1px solid rgba(16, 185, 129, 0.25)',
                padding: '1px 6px',
                borderRadius: '4px',
                fontWeight: 600,
                letterSpacing: '0.02em',
              }}
            >
              {version}
            </span>
          )}
        </div>
      )}
    </div>
  );
};
