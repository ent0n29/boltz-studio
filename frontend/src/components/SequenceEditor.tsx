import { useRef, useEffect } from 'react'

interface SequenceEditorProps {
  sequence: string
  onChange: (sequence: string) => void
  plddt?: number[]
}

// Amino acid colors (by property)
const AA_COLORS: Record<string, string> = {
  // Hydrophobic (blue)
  A: '#6366f1', L: '#6366f1', I: '#6366f1', V: '#6366f1', M: '#6366f1',
  F: '#6366f1', W: '#6366f1', P: '#6366f1',
  // Polar (green)
  S: '#22c55e', T: '#22c55e', N: '#22c55e', Q: '#22c55e', C: '#22c55e', Y: '#22c55e',
  // Charged positive (red)
  K: '#ef4444', R: '#ef4444', H: '#f97316',
  // Charged negative (purple)
  D: '#a855f7', E: '#a855f7',
  // Special (yellow)
  G: '#eab308',
}

export function SequenceEditor({ sequence, onChange, plddt }: SequenceEditorProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Clean sequence input
  const handleChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value
      .toUpperCase()
      .replace(/[^ACDEFGHIKLMNPQRSTVWY\n]/g, '')
    onChange(value)
  }

  // Calculate stats
  const length = sequence.replace(/\n/g, '').length
  const avgPlddt = plddt && plddt.length > 0
    ? (plddt.reduce((a, b) => a + b, 0) / plddt.length * 100).toFixed(1)
    : null

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <textarea
        ref={textareaRef}
        className="sequence-input"
        value={sequence}
        onChange={handleChange}
        placeholder="Enter protein sequence (e.g., MVTPEG...)"
        spellCheck={false}
      />
      <div className="sequence-stats">
        <span>Length: {length} aa</span>
        {avgPlddt && <span>Avg pLDDT: {avgPlddt}%</span>}
      </div>

      {/* Amino acid legend */}
      <div style={{
        marginTop: '0.5rem',
        display: 'flex',
        flexWrap: 'wrap',
        gap: '0.25rem',
        fontSize: '0.625rem',
      }}>
        <span style={{ color: '#6366f1' }}>■ Hydrophobic</span>
        <span style={{ color: '#22c55e' }}>■ Polar</span>
        <span style={{ color: '#ef4444' }}>■ Basic</span>
        <span style={{ color: '#a855f7' }}>■ Acidic</span>
        <span style={{ color: '#eab308' }}>■ Glycine</span>
      </div>
    </div>
  )
}
