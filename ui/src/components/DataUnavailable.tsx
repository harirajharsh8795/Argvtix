import React from 'react';
import { AlertCircle, RefreshCw } from 'lucide-react';

interface DataUnavailableProps {
  title?: string;
  message?: string;
  onRetry?: () => void;
  style?: React.CSSProperties;
}

export const DataUnavailable: React.FC<DataUnavailableProps> = ({
  title = 'Data unavailable',
  message = 'Could not load data from the Argvtix backend. Please verify your connection or service status and try again.',
  onRetry,
  style,
}) => {
  return (
    <div
      className="card"
      style={{
        padding: '36px 24px',
        textAlign: 'center',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '12px',
        background: 'var(--bg-surface)',
        border: '1px dashed var(--border-default)',
        borderRadius: 'var(--radius-md)',
        ...style,
      }}
    >
      <AlertCircle size={36} color="var(--accent-warning)" />
      <div>
        <h3 style={{ fontSize: '1.05rem', fontWeight: 600, color: 'var(--text-bright)', margin: 0 }}>
          {title}
        </h3>
        <p style={{ fontSize: '0.84rem', color: 'var(--text-secondary)', marginTop: '6px', maxWidth: '480px' }}>
          {message}
        </p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="btn btn-secondary btn-sm"
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '6px',
            marginTop: '8px',
            cursor: 'pointer',
          }}
        >
          <RefreshCw size={14} />
          <span>Retry</span>
        </button>
      )}
    </div>
  );
};
