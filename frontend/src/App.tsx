import { useState } from 'react'
import './index.css'
import { VideoKyc } from './VideoKyc'

function App() {
  const [caseId, setCaseId] = useState<string>('')
  const [started, setStarted] = useState<boolean>(false)

  if (started && caseId.trim()) {
    return <VideoKyc caseId={caseId.trim()} onExit={() => setStarted(false)} />
  }

  return (
    <div className="landing-container" style={{
      display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
      height: '100vh', backgroundColor: '#0d1117', color: '#c9d1d9', fontFamily: 'Inter, sans-serif'
    }}>
      <div style={{
        background: '#161b22', padding: '3rem', borderRadius: '16px',
        boxShadow: '0 20px 40px rgba(0,0,0,0.4)', border: '1px solid #30363d',
        textAlign: 'center', maxWidth: '400px', width: '100%'
      }}>
        <h1 style={{ color: '#e6edf3', marginBottom: '1rem', marginTop: 0 }}>Start Video KYC</h1>
        <p style={{ color: '#8b949e', marginBottom: '2rem' }}>
          Enter your KYC Case ID to begin the verification process.
        </p>
        <input 
          type="text" 
          value={caseId}
          onChange={e => setCaseId(e.target.value)}
          placeholder="e.g. 123e4567-e89b-12d3-a456-426614174000"
          style={{
            width: '100%', padding: '0.75rem', borderRadius: '8px',
            border: '1px solid #30363d', background: '#0d1117', color: '#c9d1d9',
            marginBottom: '1.5rem', boxSizing: 'border-box'
          }}
        />
        <button 
          onClick={() => setStarted(true)}
          disabled={!caseId.trim()}
          style={{
            width: '100%', padding: '0.75rem', borderRadius: '8px',
            border: 'none', background: 'linear-gradient(180deg, #238636 0%, #2ea043 100%)',
            color: 'white', fontWeight: 600, cursor: caseId ? 'pointer' : 'not-allowed',
            opacity: caseId ? 1 : 0.5
          }}
        >
          Begin Session
        </button>
      </div>
    </div>
  )
}

export default App
