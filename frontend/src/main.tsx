import React from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'

type Category = { name: string; description: string }
type Settings = { categories: Category[] }

function App() {
  const [categories, setCategories] = React.useState<Category[]>([])
  const [message, setMessage] = React.useState('Loading categories…')
  const [error, setError] = React.useState(false)
  const load = React.useCallback(async () => {
    try {
      const response = await fetch('/settings')
      if (!response.ok) throw new Error(`API returned HTTP ${response.status}`)
      const result: Settings = await response.json()
      setCategories(result.categories)
      setMessage('Categories loaded. Changes apply to future processing.')
      setError(false)
    } catch (reason) {
      setMessage(`Connection error: ${reason instanceof Error ? reason.message : 'Unable to reach API'}`)
      setError(true)
    }
  }, [])
  React.useEffect(() => { void load() }, [load])
  function update(index: number, field: keyof Category, value: string) {
    setCategories(current => current.map((category, i) => i === index ? { ...category, [field]: value } : category))
  }
  async function save(event: React.FormEvent) {
    event.preventDefault()
    setMessage('Saving categories…')
    try {
      const response = await fetch('/settings', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ categories }) })
      const result = await response.json()
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : `API returned HTTP ${response.status}`)
      setCategories(result.categories)
      setMessage('Categories saved successfully.')
      setError(false)
    } catch (reason) {
      setMessage(`Save failed: ${reason instanceof Error ? reason.message : 'Unable to reach API'}`)
      setError(true)
    }
  }
  return <main>
    <header><div className="eyebrow">LOCAL DOCUMENT ORGANIZER</div><h1>Download Classify</h1><p>Define the topics that will organize your documents.</p></header>
    <form onSubmit={save}>
      <div className="section-heading"><div><h2>Topic categories</h2><p>Edit names and descriptions. NeedsReview is reserved.</p></div></div>
      <div className="categories">{categories.map((category, index) => <fieldset key={index}>
        <label>Category name<input required maxLength={120} value={category.name} onChange={event => update(index, 'name', event.target.value)} /></label>
        <label>Description<textarea maxLength={2000} rows={3} value={category.description} onChange={event => update(index, 'description', event.target.value)} /></label>
      </fieldset>)}</div>
      <div className="actions"><button type="submit" disabled={!categories.length}>Save categories</button><output className={error ? 'status error' : 'status'} role="status">{message}</output></div>
    </form>
    <footer>Settings are stored locally on this Mac. Editing affects future processing only.</footer>
  </main>
}

createRoot(document.getElementById('root')!).render(<App />)
