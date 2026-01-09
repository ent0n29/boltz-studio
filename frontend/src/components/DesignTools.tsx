interface DesignToolsProps {
  onPredict: () => void
  onRandomMutate: () => void
  isRunning: boolean
  sequence: string
}

export function DesignTools({
  onPredict,
  onRandomMutate,
  isRunning,
  sequence,
}: DesignToolsProps) {
  const isValidSequence = sequence.length >= 10 && sequence.length <= 500

  return (
    <div className="btn-group" style={{ flexDirection: 'column', gap: '0.75rem' }}>
      {/* Main predict button */}
      <button
        className="btn btn-primary"
        onClick={onPredict}
        disabled={isRunning || !isValidSequence}
        style={{ width: '100%', justifyContent: 'center' }}
      >
        {isRunning ? (
          <>
            <Spinner /> Predicting...
          </>
        ) : (
          <>
            <ProteinIcon /> Predict Structure
          </>
        )}
      </button>

      {/* Design actions */}
      <div className="btn-group">
        <button
          className="btn btn-secondary"
          onClick={onRandomMutate}
          disabled={isRunning || !isValidSequence}
          title="Introduce a random mutation"
        >
          <DiceIcon /> Random Mutate
        </button>
      </div>

      {/* Validation message */}
      {!isValidSequence && (
        <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
          Sequence should be 10-500 amino acids
        </p>
      )}

      {/* Tips */}
      <div style={{
        marginTop: '0.5rem',
        padding: '0.75rem',
        background: 'var(--bg-tertiary)',
        borderRadius: '8px',
        fontSize: '0.75rem',
        color: 'var(--text-secondary)',
      }}>
        <strong style={{ color: 'var(--text-primary)' }}>Tips:</strong>
        <ul style={{ marginTop: '0.5rem', paddingLeft: '1rem' }}>
          <li>Shorter sequences predict faster</li>
          <li>Use single-letter amino acid codes</li>
          <li>Try mutating low-confidence regions</li>
        </ul>
      </div>
    </div>
  )
}

// Icons
function ProteinIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
    </svg>
  )
}

function DiceIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="3" width="18" height="18" rx="2" />
      <circle cx="8" cy="8" r="1" fill="currentColor" />
      <circle cx="16" cy="8" r="1" fill="currentColor" />
      <circle cx="8" cy="16" r="1" fill="currentColor" />
      <circle cx="16" cy="16" r="1" fill="currentColor" />
      <circle cx="12" cy="12" r="1" fill="currentColor" />
    </svg>
  )
}

function Spinner() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      style={{ animation: 'spin 1s linear infinite' }}
    >
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      <path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83" />
    </svg>
  )
}
