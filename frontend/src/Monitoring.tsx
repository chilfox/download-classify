import React from 'react'

type Status = {
  folder: string
  mode: 'automatic' | 'suggestions-only'
  monitoring: boolean
  processing: string | null
  model_status: string
  model_error: string | null
  monitor_error: string | null
}
type Result = {
  filename: string
  outcome: string
  suggestion: string | null
  destination: string | null
  recorded: boolean | null
  recording_error: string | null
  scores: Record<string, number> | null
  reason: string
  truncated: boolean | null
  encoded_tokens: number | null
}

async function api<T>(path: string, method = 'GET', signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { method, signal })
  const body = await response.json().catch(() => null)
  if (!response.ok) throw new Error(typeof body?.detail === 'string' ? body.detail : `API returned HTTP ${response.status}`)
  return body as T
}

export function Monitoring() {
  const [status, setStatus] = React.useState<Status | null>(null)
  const [results, setResults] = React.useState<Result[]>([])
  const [connectionError, setConnectionError] = React.useState('')
  const [actionError, setActionError] = React.useState('')
  const [pending, setPending] = React.useState(false)
  React.useEffect(() => {
    const controller = new AbortController()
    let timer: ReturnType<typeof setTimeout>
    async function poll() {
      try {
        const [nextStatus, nextResults] = await Promise.all([
          api<Status>('/status', 'GET', controller.signal),
          api<Result[]>('/results', 'GET', controller.signal),
        ])
        if (!controller.signal.aborted) {
          setStatus(nextStatus)
          setResults(nextResults)
          setConnectionError('')
        }
      } catch (reason) {
        if (!controller.signal.aborted) setConnectionError(`Connection error: ${reason instanceof Error ? reason.message : 'Unable to reach API'}. Status and results may be stale.`)
      } finally {
        if (!controller.signal.aborted) timer = setTimeout(() => { void poll() }, 1000)
      }
    }
    void poll()
    return () => { controller.abort(); clearTimeout(timer) }
  }, [])

  async function control(action: 'start' | 'stop') {
    setPending(true)
    setActionError('')
    try {
      setStatus(await api<Status>(`/monitor/${action}`, 'POST'))
    } catch (reason) {
      setActionError(`${action === 'start' ? 'Start' : 'Stop'} failed: ${reason instanceof Error ? reason.message : 'Unable to reach API'}`)
    } finally { setPending(false) }
  }

  return <section className="monitoring" aria-labelledby="monitoring-title">
    <div className="section-heading"><h2 id="monitoring-title">Monitoring</h2><p>{status?.mode === 'automatic' ? 'Automatic mode: clear results move to a topic folder; uncertain results move to NeedsReview. File contents are never modified.' : status?.mode === 'suggestions-only' ? 'Suggestions-only fallback. No files are moved, deleted, or modified.' : 'Operating mode will appear when connected.'}</p></div>
    <p className="notice">Use disposable documents in a dedicated demo folder. Only new root-level TXT and Markdown files are classified. Existing files, nested files, symlinks, and temporary downloads are excluded.</p>
    {!status && !connectionError && <p role="status">Loading monitoring status…</p>}
    {status && <>
      <dl className="monitor-details">
        <div><dt>Operating mode</dt><dd>{status.mode}</dd></div>
        <div><dt>Monitored folder</dt><dd>{status.folder}</dd></div>
        <div><dt>Local model</dt><dd>{status.model_status === 'loading' ? 'Loading local model…' : status.model_status === 'not-loaded' ? 'Not loaded - start monitoring to load cached weights' : status.model_status}</dd></div>
        <div><dt>Monitoring</dt><dd>{status.monitoring ? 'Watching for new stable files' : 'Stopped'}{status.processing ? ` - ${status.monitoring ? 'Processing' : 'Finishing active attempt'}: ${status.processing}` : ''}</dd></div>
      </dl>
      {status.model_error && <p className="status error" role="alert">{status.model_error}</p>}
      {status.monitor_error && <p className="status error" role="alert">{status.monitor_error}</p>}
      <div className="actions">
        <button disabled={pending || status.monitoring || Boolean(status.processing) || Boolean(connectionError)} onClick={() => { void control('start') }}>Start monitoring</button>
        <button className="secondary" disabled={pending || !status.monitoring} onClick={() => { void control('stop') }}>Stop monitoring</button>
        {pending && <span role="status">Updating monitoring…</span>}
      </div>
      {status.processing && <p className="notice" role="status">Stopping prevents new attempts. The active attempt may finish; restart is available after it finishes.</p>}
    </>}
    {connectionError && <p className="status error" role="alert">{connectionError}</p>}
    {actionError && <p className="status error" role="alert">{actionError}</p>}
    <div className="section-heading results-heading"><h2>Current-run results ({results.length})</h2><p>Model scores are independent sigmoid scores, not probabilities of correctness. Fixed thresholds: score 0.65, top-two gap 0.10.</p></div>
    {!results.length && <p className="notice">No results yet. Start monitoring, then add a new document. All PDFs are unsupported and stay untouched.</p>}
    <ol className="results">{results.map((result, index) => <li key={index}>
      <div className="result-heading"><strong>{result.filename}</strong><span className={`badge ${result.outcome === 'failed' ? 'failure' : ''}`}>{result.outcome}</span></div>
      {result.suggestion && <p>Classification: <strong>{result.suggestion}</strong></p>}
      {result.destination && <p className="input-disclosure">Destination: <strong>{result.destination}</strong></p>}
      {result.recorded === true && <p className="notice">Movement trace saved locally.</p>}
      {result.recording_error && <p className="status error" role="alert">{result.recording_error}</p>}
      {result.scores && <dl className="scores" aria-label="Model scores">{Object.entries(result.scores).map(([name, score]) => <div key={name}><dt>{name}</dt><dd>{score.toFixed(3)}</dd></div>)}</dl>}
      {result.truncated !== null && <p className="input-disclosure">{result.truncated ? 'Excerpt only - the full document was NOT considered. Long-document quality is unvalidated.' : 'Complete bounded opening considered; no truncation.'}{result.encoded_tokens !== null ? ` Encoded input: ${result.encoded_tokens}/512 tokens.` : ''}</p>}
      <p className={result.outcome === 'failed' ? 'status error' : 'notice'}>{result.reason}</p>
    </li>)}</ol>
  </section>
}
