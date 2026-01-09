interface MetricsBarProps {
  confidence?: number
  plddt?: number
  ptm?: number
  sequenceLength: number
}

export function MetricsBar({ confidence, plddt, ptm, sequenceLength }: MetricsBarProps) {
  const getConfidenceClass = (value?: number) => {
    if (value === undefined) return ''
    if (value >= 0.8) return 'high'
    if (value >= 0.5) return 'medium'
    return 'low'
  }

  return (
    <div className="metrics-bar">
      <div className="metric">
        <span className="metric-label">Sequence Length</span>
        <span className="metric-value">{sequenceLength} aa</span>
      </div>

      <div className="metric">
        <span className="metric-label">Confidence Score</span>
        <span className={`metric-value ${getConfidenceClass(confidence)}`}>
          {confidence !== undefined ? (confidence * 100).toFixed(1) + '%' : '—'}
        </span>
      </div>

      <div className="metric">
        <span className="metric-label">pLDDT</span>
        <span className={`metric-value ${getConfidenceClass(plddt)}`}>
          {plddt !== undefined ? (plddt * 100).toFixed(1) + '%' : '—'}
        </span>
      </div>

      <div className="metric">
        <span className="metric-label">pTM</span>
        <span className={`metric-value ${getConfidenceClass(ptm)}`}>
          {ptm !== undefined ? (ptm * 100).toFixed(1) + '%' : '—'}
        </span>
      </div>

      {/* Legend */}
      <div style={{
        marginLeft: 'auto',
        display: 'flex',
        alignItems: 'center',
        gap: '1rem',
        fontSize: '0.75rem',
        color: 'var(--text-secondary)',
      }}>
        <span><span style={{ color: 'var(--success)' }}>●</span> High (&gt;80%)</span>
        <span><span style={{ color: 'var(--warning)' }}>●</span> Medium (50-80%)</span>
        <span><span style={{ color: 'var(--error)' }}>●</span> Low (&lt;50%)</span>
      </div>
    </div>
  )
}
