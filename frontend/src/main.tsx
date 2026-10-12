import React from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'

function App() {
  const [health, setHealth] = React.useState<string>('Checking API…')
  React.useEffect(() => {
    fetch('/health')
      .then(async (response) => {
        if (!response.ok) throw new Error(`API returned HTTP ${response.status}`)
        const result: { status: string } = await response.json()
        setHealth(`API status: ${result.status}`)
      })
      .catch((error: unknown) => setHealth(`Connection error: ${error instanceof Error ? error.message : 'Unable to reach API'}`))
  }, [])
  return <main><h1>Download Classify</h1><p>Local API connectivity</p><output role="status">{health}</output></main>
}

createRoot(document.getElementById('root')!).render(<App />)
