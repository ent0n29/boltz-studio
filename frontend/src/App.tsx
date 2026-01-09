import { useState, useEffect, useRef, useCallback } from 'react'
import { MolstarViewer } from './components/MolstarViewer'
import { SequenceEditor } from './components/SequenceEditor'
import { DesignTools } from './components/DesignTools'
import { MetricsBar } from './components/MetricsBar'
import { api, JobStatus, PredictionResult } from './api'

// Example protein sequence (small, fast to predict)
const EXAMPLE_SEQUENCE = "MKLAVLKAGIAQGEVLVN"

interface AppState {
  sequence: string
  chainId: string
  jobId: string | null
  status: JobStatus | null
  result: PredictionResult | null
  error: string | null
}

function App() {
  const [state, setState] = useState<AppState>({
    sequence: EXAMPLE_SEQUENCE,
    chainId: 'A',
    jobId: null,
    status: null,
    result: null,
    error: null,
  })

  const pollingRef = useRef<number | null>(null)

  // Poll for job status
  const pollJobStatus = useCallback(async (jobId: string) => {
    try {
      const status = await api.getJobStatus(jobId)
      setState(prev => ({ ...prev, status }))

      if (status.status === 'completed' && status.result) {
        setState(prev => ({
          ...prev,
          result: status.result as PredictionResult,
          error: null,
        }))
        if (pollingRef.current) {
          clearInterval(pollingRef.current)
          pollingRef.current = null
        }
      } else if (status.status === 'failed') {
        setState(prev => ({
          ...prev,
          error: status.error || 'Prediction failed',
        }))
        if (pollingRef.current) {
          clearInterval(pollingRef.current)
          pollingRef.current = null
        }
      }
    } catch (err) {
      console.error('Error polling job status:', err)
    }
  }, [])

  // Start prediction
  const handlePredict = async () => {
    try {
      setState(prev => ({
        ...prev,
        jobId: null,
        status: null,
        result: null,
        error: null,
      }))

      const response = await api.predict({
        sequences: [{
          id: state.chainId,
          sequence: state.sequence,
          type: 'protein',
        }],
        name: 'design',
        recycling_steps: 1,
        sampling_steps: 50,
        diffusion_samples: 1,
      })

      setState(prev => ({
        ...prev,
        jobId: response.job_id,
        status: response,
      }))

      // Start polling
      pollingRef.current = window.setInterval(() => {
        pollJobStatus(response.job_id)
      }, 2000)

    } catch (err: any) {
      setState(prev => ({
        ...prev,
        error: err.message || 'Failed to start prediction',
      }))
    }
  }

  // Handle sequence change
  const handleSequenceChange = (sequence: string) => {
    setState(prev => ({ ...prev, sequence }))
  }

  // Handle mutation
  const handleMutate = async (position: number, newAA: string) => {
    const seq = state.sequence.split('')
    seq[position] = newAA
    setState(prev => ({ ...prev, sequence: seq.join('') }))
  }

  // Random mutation
  const handleRandomMutate = async () => {
    try {
      const response = await api.randomMutate(state.sequence, 1)
      setState(prev => ({ ...prev, sequence: response.mutated_sequence }))
    } catch (err: any) {
      console.error('Random mutate failed:', err)
    }
  }

  // Cleanup polling on unmount
  useEffect(() => {
    return () => {
      if (pollingRef.current) {
        clearInterval(pollingRef.current)
      }
    }
  }, [])

  const confidence = state.result?.confidence
  const isRunning = state.status?.status === 'running' || state.status?.status === 'queued'

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <h1>
          <span>Boltz</span>Studio
        </h1>
        <div style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
          {state.status && (
            <span className={`status-badge ${state.status.status}`}>
              {state.status.status}
            </span>
          )}
        </div>
      </header>

      {/* Main Content */}
      <main className="main">
        {/* Sidebar */}
        <aside className="sidebar">
          {/* Sequence Editor */}
          <div className="sidebar-section sequence-editor">
            <h3>Sequence</h3>
            <SequenceEditor
              sequence={state.sequence}
              onChange={handleSequenceChange}
              plddt={state.result?.plddt_per_residue}
            />
          </div>

          {/* Design Tools */}
          <div className="sidebar-section">
            <h3>Design Tools</h3>
            <DesignTools
              onPredict={handlePredict}
              onRandomMutate={handleRandomMutate}
              isRunning={isRunning}
              sequence={state.sequence}
            />

            {/* Progress */}
            {state.status && isRunning && (
              <div className="progress-container">
                <div className="progress-bar">
                  <div
                    className="progress-fill"
                    style={{ width: `${(state.status.progress || 0) * 100}%` }}
                  />
                </div>
                <div className="progress-text">
                  {state.status.status === 'queued' ? 'Queued...' :
                   `Predicting structure... ${Math.round((state.status.progress || 0) * 100)}%`}
                </div>
              </div>
            )}

            {/* Error */}
            {state.error && (
              <div style={{ marginTop: '1rem', color: 'var(--error)', fontSize: '0.875rem' }}>
                Error: {state.error}
              </div>
            )}
          </div>
        </aside>

        {/* Viewer */}
        <div className="viewer-container">
          <div className="viewer">
            {state.result?.structure_pdb ? (
              <MolstarViewer
                pdbData={state.result.structure_pdb}
                plddt={state.result.plddt_per_residue}
              />
            ) : (
              <div className="viewer-placeholder">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                  <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
                </svg>
                <p>Enter a sequence and click "Predict Structure"</p>
                <p style={{ fontSize: '0.75rem', opacity: 0.7 }}>
                  3D structure will appear here
                </p>
              </div>
            )}
          </div>
        </div>
      </main>

      {/* Metrics Bar */}
      <MetricsBar
        confidence={confidence?.confidence_score}
        plddt={confidence?.complex_plddt}
        ptm={confidence?.ptm}
        sequenceLength={state.sequence.length}
      />
    </div>
  )
}

export default App
