import { useEffect, useRef, useState } from 'react'

interface MolstarViewerProps {
  pdbData: string
  plddt?: number[]
}

// Simple WebGL-based PDB viewer (lightweight alternative to full Mol*)
export function MolstarViewer({ pdbData, plddt }: MolstarViewerProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const [error, setError] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    if (!pdbData || !containerRef.current) return

    setIsLoading(true)
    setError(null)

    // For now, use a simple 3Dmol.js viewer (lighter weight than Mol*)
    // Load 3Dmol.js dynamically
    const loadViewer = async () => {
      try {
        // Check if 3Dmol is already loaded
        if (!(window as any).$3Dmol) {
          // Load 3Dmol.js from CDN
          const script = document.createElement('script')
          script.src = 'https://3dmol.org/build/3Dmol-min.js'
          script.async = true
          await new Promise((resolve, reject) => {
            script.onload = resolve
            script.onerror = reject
            document.head.appendChild(script)
          })
        }

        const $3Dmol = (window as any).$3Dmol

        // Clear previous viewer
        containerRef.current!.innerHTML = ''

        // Create viewer
        const viewer = $3Dmol.createViewer(containerRef.current, {
          backgroundColor: '#000000',
          antialias: true,
        })

        // Add model
        viewer.addModel(pdbData, 'pdb')

        // Color by pLDDT if available
        if (plddt && plddt.length > 0) {
          // Color scheme based on pLDDT (AlphaFold style)
          viewer.setStyle({}, {
            cartoon: {
              colorfunc: (atom: any) => {
                const residueIndex = atom.resi - 1
                const confidence = plddt[residueIndex] ?? 0.5

                // AlphaFold confidence colors
                if (confidence > 0.9) return '#0053D6'  // Very high (blue)
                if (confidence > 0.7) return '#65CBF3'  // High (light blue)
                if (confidence > 0.5) return '#FFDB13'  // Medium (yellow)
                return '#FF7D45'  // Low (orange)
              }
            }
          })
        } else {
          // Default coloring (rainbow by residue)
          viewer.setStyle({}, {
            cartoon: { color: 'spectrum' }
          })
        }

        viewer.zoomTo()
        viewer.render()

        // Add spin animation on hover
        let spinning = false
        containerRef.current!.addEventListener('mouseenter', () => {
          spinning = true
          const spin = () => {
            if (spinning) {
              viewer.rotate(1, 'y')
              viewer.render()
              requestAnimationFrame(spin)
            }
          }
          spin()
        })
        containerRef.current!.addEventListener('mouseleave', () => {
          spinning = false
        })

        setIsLoading(false)
      } catch (err: any) {
        console.error('Failed to load viewer:', err)
        setError(err.message || 'Failed to load 3D viewer')
        setIsLoading(false)
      }
    }

    loadViewer()
  }, [pdbData, plddt])

  return (
    <div
      ref={containerRef}
      style={{
        width: '100%',
        height: '100%',
        position: 'relative',
      }}
    >
      {isLoading && (
        <div style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#000',
          color: '#666',
        }}>
          Loading 3D viewer...
        </div>
      )}
      {error && (
        <div style={{
          position: 'absolute',
          inset: 0,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#000',
          color: '#ef4444',
          padding: '2rem',
          textAlign: 'center',
        }}>
          <p>Failed to load 3D viewer</p>
          <p style={{ fontSize: '0.75rem', opacity: 0.7, marginTop: '0.5rem' }}>
            {error}
          </p>
        </div>
      )}

      {/* pLDDT Legend */}
      {!isLoading && !error && plddt && (
        <div style={{
          position: 'absolute',
          bottom: '1rem',
          left: '1rem',
          background: 'rgba(0,0,0,0.8)',
          padding: '0.75rem',
          borderRadius: '8px',
          fontSize: '0.625rem',
          color: '#fff',
        }}>
          <div style={{ marginBottom: '0.5rem', fontWeight: 600 }}>pLDDT Confidence</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ width: 12, height: 12, background: '#0053D6', borderRadius: 2 }} />
              Very high (&gt;90%)
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ width: 12, height: 12, background: '#65CBF3', borderRadius: 2 }} />
              High (70-90%)
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ width: 12, height: 12, background: '#FFDB13', borderRadius: 2 }} />
              Medium (50-70%)
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span style={{ width: 12, height: 12, background: '#FF7D45', borderRadius: 2 }} />
              Low (&lt;50%)
            </div>
          </div>
        </div>
      )}

      {/* Controls hint */}
      {!isLoading && !error && (
        <div style={{
          position: 'absolute',
          bottom: '1rem',
          right: '1rem',
          background: 'rgba(0,0,0,0.8)',
          padding: '0.5rem 0.75rem',
          borderRadius: '8px',
          fontSize: '0.625rem',
          color: '#888',
        }}>
          Drag to rotate • Scroll to zoom • Hover to spin
        </div>
      )}
    </div>
  )
}
