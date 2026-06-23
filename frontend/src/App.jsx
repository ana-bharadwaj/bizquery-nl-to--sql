import { useState, useEffect, useRef } from 'react'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL

function App() {
  const [question, setQuestion] = useState('')
  const [loading, setLoading] = useState(false)
  const [status, setStatus] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState(null)

  const [csvFile, setCsvFile] = useState(null)
  const [tableName, setTableName] = useState('')
  const [uploadStatus, setUploadStatus] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const [tables, setTables] = useState([])
  const fileInputRef = useRef(null)

  const [connections, setConnections] = useState([])
  const [activeConnectionId, setActiveConnectionId] = useState(0)
  const [showAddConnection, setShowAddConnection] = useState(false)
  const [newConnName, setNewConnName] = useState('')
  const [newConnString, setNewConnString] = useState('')
  const [connectingStatus, setConnectingStatus] = useState(null)
  const [connecting, setConnecting] = useState(false)

  const fetchTables = async () => {
    try {
      const res = await fetch(`${API_URL}/tables`)
      const data = await res.json()
      setTables(data.tables || [])
    } catch (err) {
      // silent fail
    }
  }

  const fetchConnections = async () => {
    try {
      const res = await fetch(`${API_URL}/connections`)
      const data = await res.json()
      setConnections(data.connections || [])
    } catch (err) {
      // silent fail
    }
  }

  useEffect(() => {
    fetchTables()
    fetchConnections()
  }, [])

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!question.trim()) return

    setLoading(true)
    setError(null)
    setResult(null)
    setStatus('')

    const url = `${API_URL}/query-stream?question=${encodeURIComponent(question)}&connection_id=${activeConnectionId}`
    const eventSource = new EventSource(url)

    eventSource.addEventListener('status', (e) => {
      const data = JSON.parse(e.data)
      setStatus(data.message)
    })

    eventSource.addEventListener('result', (e) => {
      const data = JSON.parse(e.data)
      setResult(data)
      setLoading(false)
      setStatus('')
      eventSource.close()
    })

    eventSource.addEventListener('error', (e) => {
      if (e.data) {
        const data = JSON.parse(e.data)
        setError(data.message)
      } else {
        setError('Connection lost. Is the backend running?')
      }
      setLoading(false)
      setStatus('')
      eventSource.close()
    })
  }

  const doUpload = async (file) => {
    setUploading(true)
    setUploadStatus(null)

    const formData = new FormData()
    formData.append('file', file)

    const url = `${API_URL}/upload-csv${tableName ? `?table_name=${encodeURIComponent(tableName)}` : ''}`

    try {
      const response = await fetch(url, { method: 'POST', body: formData })
      const data = await response.json()
      setUploadStatus(data)
      if (data.success) {
        setCsvFile(null)
        setTableName('')
        fetchTables()
      }
    } catch (err) {
      setUploadStatus({ success: false, error: 'Could not reach the backend.' })
    } finally {
      setUploading(false)
    }
  }

  const handleFileSelect = (file) => {
    if (file && file.name.endsWith('.csv')) {
      setCsvFile(file)
      setUploadStatus(null)
    }
  }

  const handleDrop = (e) => {
    e.preventDefault()
    setDragActive(false)
    const file = e.dataTransfer.files[0]
    handleFileSelect(file)
  }

  const handleAddConnection = async (e) => {
    e.preventDefault()
    if (!newConnName.trim() || !newConnString.trim()) return

    setConnecting(true)
    setConnectingStatus(null)

    const url = `${API_URL}/connections?name=${encodeURIComponent(newConnName)}&connection_string=${encodeURIComponent(newConnString)}`

    try {
      const res = await fetch(url, { method: 'POST' })
      const data = await res.json()
      setConnectingStatus(data)
      if (data.success) {
        setNewConnName('')
        setNewConnString('')
        fetchConnections()
        setActiveConnectionId(data.id)
        setTimeout(() => setShowAddConnection(false), 1200)
      }
    } catch (err) {
      setConnectingStatus({ success: false, error: 'Could not reach the backend.' })
    } finally {
      setConnecting(false)
    }
  }

  return (
    <div className="app">
      <p className="eyebrow">Plain English → SQL</p>
      <h1>BizQuery</h1>
      <p className="subtitle">Ask your data a question. Get the query, the numbers, and the answer — no SQL required.</p>
      <div className="court-line"></div>

      <div className="data-panel">
        <div className="data-panel-header">
          <h2>Database</h2>
          <button type="button" className="link-btn" onClick={() => setShowAddConnection(!showAddConnection)}>
            {showAddConnection ? 'Cancel' : '+ Connect a database'}
          </button>
        </div>

        <div className="connection-select">
          {connections.map((c) => (
            <button
              key={c.id}
              type="button"
              className={`conn-chip ${activeConnectionId === c.id ? 'conn-chip-active' : ''}`}
              onClick={() => setActiveConnectionId(c.id)}
            >
              {c.name}
            </button>
          ))}
        </div>

        {showAddConnection && (
          <form onSubmit={handleAddConnection} className="connection-form">
            <input
              type="text"
              placeholder="Connection name (e.g. My Production DB)"
              value={newConnName}
              onChange={(e) => setNewConnName(e.target.value)}
            />
            <input
              type="password"
              placeholder="postgresql://user:password@host:5432/dbname"
              value={newConnString}
              onChange={(e) => setNewConnString(e.target.value)}
            />
            <button type="submit" disabled={connecting}>
              {connecting ? 'Testing connection...' : 'Connect'}
            </button>
          </form>
        )}

        {connectingStatus && (
          <div className={connectingStatus.success ? 'upload-success' : 'error-box'}>
            {connectingStatus.success ? `Connected to "${connectingStatus.name}"` : connectingStatus.error}
          </div>
        )}
      </div>

      <div className="data-panel">
        <div className="data-panel-header">
          <h2>Data Sources</h2>
          <span className="table-count">{tables.length} table{tables.length !== 1 ? 's' : ''} loaded</span>
        </div>

        {tables.length > 0 && (
          <div className="table-chips">
            {tables.map((t) => (
              <span key={t} className="table-chip">{t}</span>
            ))}
          </div>
        )}

        <div
          className={`dropzone ${dragActive ? 'dropzone-active' : ''} ${csvFile ? 'dropzone-filled' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setDragActive(true) }}
          onDragLeave={() => setDragActive(false)}
          onDrop={handleDrop}
          onClick={() => fileInputRef.current.click()}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            onChange={(e) => handleFileSelect(e.target.files[0])}
            hidden
          />
          {csvFile ? (
            <p className="dropzone-text">
              <span className="file-icon">▤</span> {csvFile.name}
            </p>
          ) : (
            <p className="dropzone-text">
              Drop a CSV here, or <span className="dropzone-link">browse</span>
            </p>
          )}
        </div>

        {csvFile && (
          <div className="upload-controls">
            <input
              type="text"
              placeholder="table name (optional)"
              value={tableName}
              onChange={(e) => setTableName(e.target.value)}
            />
            <button
              type="button"
              disabled={uploading}
              onClick={() => doUpload(csvFile)}
            >
              {uploading ? 'Loading...' : 'Add table'}
            </button>
            <button
              type="button"
              className="cancel-btn"
              onClick={() => { setCsvFile(null); setTableName('') }}
            >
              Cancel
            </button>
          </div>
        )}

        {uploadStatus && (
          <div className={uploadStatus.success ? 'upload-success' : 'error-box'}>
            {uploadStatus.success
              ? `Loaded "${uploadStatus.table_name}" — ${uploadStatus.row_count} rows, ${uploadStatus.columns.length} columns`
              : uploadStatus.error}
          </div>
        )}
      </div>

      <form onSubmit={handleSubmit} className="query-form">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="e.g. Which team scored the most total points?"
        />
        <button type="submit" disabled={loading}>
          {loading ? 'Thinking...' : 'Ask'}
        </button>
      </form>

      {loading && status && <div className="status-box">{status}</div>}
      {error && <div className="error-box">{error}</div>}

      {result && (
        <div className="result-box">
          <details className="sql-display">
            <summary>View generated SQL</summary>
            <pre>{result.sql}</pre>
          </details>

          <p className="row-count">{result.row_count} row(s) returned</p>

          <table>
            <thead>
              <tr>
                {result.columns.map((col) => (
                  <th key={col}>{col}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {result.results.map((row, i) => (
                <tr key={i}>
                  {result.columns.map((col) => (
                    <td key={col}>{String(row[col])}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default App