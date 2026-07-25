import { useState, useEffect, useRef, useCallback } from 'react'
import CodeViewer from '../components/CodeViewer'
import StoryPropsEditor from '../components/StoryPropsEditor'

type Message = {
  id: string
  role: 'user' | 'agent' | 'system'
  content: string
  agent_name: string
  status: string
  attachments: { type: string; label: string; content: string; language?: string }[]
  needs_reply: boolean
  suggestions: string[]
  phase: string
  error?: string
  timestamp: number
}

type AgentState = {
  name: string
  status: string
}

export default function Home() {
  const [ws, setWs] = useState<WebSocket | null>(null)
  const [sessionId, setSessionId] = useState<string>('')
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [connected, setConnected] = useState(false)
  const [agents, setAgents] = useState<AgentState[]>([])
  const [agentList, setAgentList] = useState<{ name: string; description: string }[]>([])
  const [typing, setTyping] = useState(false)
  const [characterFile, setCharacterFile] = useState<File | null>(null)
  const [charUploading, setCharUploading] = useState(false)
  const [showEditor, setShowEditor] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => {
    scrollToBottom()
  }, [messages, scrollToBottom])

  const connect = useCallback(async () => {
    const res = await fetch('/api/session', { method: 'POST' })
    const data = await res.json()
    const sid = data.session_id
    setSessionId(sid)
    setMessages(data.session.messages || [])

    const agentRes = await fetch('/api/agents')
    const agentData = await agentRes.json()
    setAgentList(agentData.agents || [])

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const socket = new WebSocket(`${protocol}//${window.location.host}/ws/${sid}`)

    socket.onopen = () => {
      setConnected(true)
    }

    socket.onmessage = (event) => {
      const data = JSON.parse(event.data)

      if (data.type === 'session_update' && data.session) {
        setMessages(data.session.messages || [])
        const states = data.session.agent_states || {}
        setAgents(
          Object.entries(states).map(([name, status]) => ({ name, status: status as string }))
        )
      }

      if (data.type === 'agent_start') {
        setTyping(true)
        setAgents(prev => {
          const existing = prev.find(a => a.name === data.agent)
          if (existing) {
            return prev.map(a => a.name === data.agent ? { ...a, status: 'working' } : a)
          }
          return [...prev, { name: data.agent, status: 'working' }]
        })
      }

      if (data.type === 'agent_done' || data.type === 'agent_output') {
        setTyping(false)
        setAgents(prev =>
          prev.map(a => a.name === data.agent ? { ...a, status: 'done' } : a)
        )
      }

      if (data.type === 'agent_error') {
        setTyping(false)
        setAgents(prev =>
          prev.map(a => a.name === data.agent ? { ...a, status: 'error' } : a)
        )
      }
    }

    socket.onclose = () => {
      setConnected(false)
    }

    setWs(socket)
  }, [])

  useEffect(() => {
    connect()
    return () => {
      ws?.close()
    }
  }, [])

  const sendMessage = useCallback(() => {
    if (!input.trim() || !ws) return
    ws.send(JSON.stringify({
      type: 'user_message',
      content: input,
    }))
    setInput('')
  }, [input, ws])

  const callAgent = useCallback((agentName: string, prompt?: string) => {
    if (!ws) return
    ws.send(JSON.stringify({
      type: 'call_agent',
      agent: agentName,
      content: prompt || '',
    }))
  }, [ws])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const renderContent = (msg: Message) => {
    const parts: JSX.Element[] = []
    
    if (msg.attachments && msg.attachments.length > 0) {
      const codeFiles = msg.attachments.filter(a => a.type === 'code')
      if (codeFiles.length > 0) {
        parts.push(
          <CodeViewer key="codeviewer" files={codeFiles} />
        )
      }
    }

    if (msg.suggestions && msg.suggestions.length > 0) {
      parts.push(
        <div key="suggestions" className="suggestions">
          {msg.suggestions.map((s, i) => (
            <button key={i} onClick={() => {
              if (s.startsWith('/agent ')) {
                const name = s.replace('/agent ', '')
                callAgent(name)
              } else if (s.startsWith('/')) {
                setInput(s)
              } else {
                setInput(s)
              }
            }}>
              {s}
            </button>
          ))}
        </div>
      )
    }

    return parts
  }

  return (
    <div className="app" dir="rtl">
      <aside className="sidebar">
        <h2>🎬 Story Studio</h2>
        <div style={{ fontSize: '0.8em', color: connected ? '#51cf66' : '#ff6b6b', marginBottom: 16 }}>
          {connected ? 'متصل' : 'قطع'}
        </div>

        <h2>🖼 کاراکتر</h2>
        <div style={{ marginBottom: 16 }}>
          <input
            type="file"
            accept="image/*"
            id="char-upload"
            style={{ display: 'none' }}
            onChange={async (e) => {
              const file = e.target.files?.[0]
              if (!file || !sessionId) return
              setCharUploading(true)
              const form = new FormData()
              form.append('file', file)
              try {
                const res = await fetch(`/api/upload/${sessionId}`, {
                  method: 'POST',
                  body: form,
                })
                const data = await res.json()
                if (data.session) {
                  setMessages(data.session.messages || [])
                }
                setCharacterFile(file)
              } catch (err) {
                console.error('Upload failed', err)
              }
              setCharUploading(false)
            }}
          />
          <button
            onClick={() => document.getElementById('char-upload')?.click()}
            style={{
              width: '100%', padding: '8px', borderRadius: 6, border: '1px dashed #4c6ef5',
              background: '#0f0f1a', color: '#91a7ff', cursor: 'pointer', fontSize: '0.85em',
            }}
          >
            {charUploading ? '⏳ در حال آپلود...' : characterFile ? '✅ ' + characterFile.name : '📁 آپلود کاراکتر'}
          </button>
        </div>

        <button
          onClick={() => setShowEditor(true)}
          style={{
            width: '100%', padding: '10px', borderRadius: 6, border: '1px solid #4c6ef5',
            background: '#4c6ef5', color: 'white', cursor: 'pointer', fontSize: '0.9em',
            marginBottom: 16, fontWeight: 600,
          }}
        >
          📊 ویرایشگر انیمیشن
        </button>

        <h2>ایجنت‌ها</h2>
        <div className="agent-list">
          {agentList.map((agent, i) => {
            const state = agents.find(a => a.name === agent.name)
            const status = state?.status || 'idle'
            return (
              <div
                key={i}
                className={`agent-item ${status}`}
                onClick={() => callAgent(agent.name)}
              >
                <div style={{ fontWeight: 600 }}>{agent.name}</div>
                <div style={{ fontSize: '0.85em', color: '#888' }}>{agent.description}</div>
                <div style={{ fontSize: '0.75em', marginTop: 4 }}>
                  {status === 'working' && '⏳ در حال اجرا...'}
                  {status === 'done' && '✅ انجام شد'}
                  {status === 'error' && '❌ خطا'}
                  {status === 'idle' && '⏸ آماده'}
                </div>
              </div>
            )
          })}
        </div>

        <div style={{ marginTop: 'auto', fontSize: '0.8em', color: '#555' }}>
          دستورات: /agents, /run, /agent [name], /code, /export, /reset
        </div>
      </aside>

      <main className="main">
        <div className="chat-header">
          <h1 style={{ fontSize: '1.2em' }}>گفتگوی استودیوی انیمیشن</h1>
          <div style={{ fontSize: '0.85em', color: '#888' }}>
            با ایجنت‌ها صحبت کنید و انیمیشن خود را بسازید
          </div>
        </div>

        <div className="chat-messages">
          {messages.map((msg, i) => (
            <div key={msg.id || i} className={`message ${msg.role}`}>
              {msg.agent_name && msg.role === 'agent' && (
                <div className="agent-name">{msg.agent_name}</div>
              )}
              <div style={{ whiteSpace: 'pre-wrap' }}>{msg.content}</div>
              {renderContent(msg)}
            </div>
          ))}
          {typing && (
            <div className="typing">
              <span></span><span></span><span></span>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        <div className="chat-input-area">
          <div className="input-row">
            <input
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="انیمیشن خود را توصیف کنید... (/ برای دستورات)"
            />
            <button onClick={sendMessage}>ارسال</button>
          </div>
        </div>
      </main>

      {showEditor && sessionId && (
        <StoryPropsEditor
          sessionId={sessionId}
          onClose={() => setShowEditor(false)}
        />
      )}
    </div>
  )
}
