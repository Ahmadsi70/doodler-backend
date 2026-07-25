import { useState, useEffect, useCallback } from 'react'
import Timeline from './Timeline'
import ShotEditor from './ShotEditor'

type StoryProps = Record<string, any>

export default function StoryPropsEditor({
  sessionId,
  onClose,
}: {
  sessionId: string
  onClose: () => void
}) {
  const [props, setProps] = useState<StoryProps | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [tab, setTab] = useState<'inspector' | 'timeline' | 'shots'>('timeline')
  const [selectedShot, setSelectedShot] = useState<number | null>(null)
  const [editingProps, setEditingProps] = useState<StoryProps | null>(null)

  useEffect(() => {
    ;(async () => {
      try {
        const res = await fetch(`/api/session/${sessionId}/story_props`)
        const data = await res.json()
        if (data.error) {
          setError(data.error)
        } else {
          setProps(data.story_props)
          setEditingProps(data.story_props)
        }
      } catch (e: any) {
        setError(e.message || 'Failed to load')
      }
      setLoading(false)
    })()
  }, [sessionId])

  const handlePropsChange = useCallback((updated: StoryProps) => {
    setEditingProps(updated)
  }, [])

  if (loading) {
    return (
      <div className="editor-overlay">
        <div className="editor-panel">
          <div className="editor-loading">در حال بارگذاری...</div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="editor-overlay">
        <div className="editor-panel">
          <div className="editor-error">{error}</div>
          <button className="editor-close-btn" onClick={onClose}>بستن</button>
        </div>
      </div>
    )
  }

  if (!props) return null

  const shots: any[] = props.shots || []
  const title = props.title || 'Story'

  return (
    <div className="editor-overlay">
      <div className="editor-panel">
        <div className="editor-header">
          <h2>📊 ویرایشگر {title}</h2>
          <div className="editor-header-info">
            {shots.length} شات | {props.fps || 24} FPS
          </div>
          <button className="editor-close-btn" onClick={onClose}>✕</button>
        </div>

        <div className="editor-tabs">
          <button className={`editor-tab ${tab === 'inspector' ? 'active' : ''}`} onClick={() => setTab('inspector')}>
            🔍 بازرس JSON
          </button>
          <button className={`editor-tab ${tab === 'timeline' ? 'active' : ''}`} onClick={() => setTab('timeline')}>
            📅 تایملاین
          </button>
          <button className={`editor-tab ${tab === 'shots' ? 'active' : ''}`} onClick={() => setTab('shots')}>
            🎬 شات‌ها
          </button>
        </div>

        <div className="editor-body">
          {tab === 'inspector' && (
            <JSONInspector data={editingProps || props} onChange={handlePropsChange} />
          )}
          {tab === 'timeline' && (
            <Timeline
              shots={shots}
              fps={props.fps || 24}
              selectedShot={selectedShot}
              onSelectShot={(id) => { setSelectedShot(id); setTab('shots') }}
            />
          )}
          {tab === 'shots' && (
            <div className="editor-shots-list">
              {shots.length === 0 && <div className="editor-empty">هیچ شاتی وجود ندارد</div>}
              {shots.map((shot: any, i: number) => (
                <ShotEditor
                  key={shot.shotId ?? i}
                  shot={shot}
                  shotIndex={i}
                  isSelected={selectedShot === (shot.shotId ?? i)}
                  onSelect={() => setSelectedShot(shot.shotId ?? i)}
                  allProps={editingProps || props}
                  onPropsChange={handlePropsChange}
                />
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function JSONInspector({
  data,
  onChange,
  path = '',
}: {
  data: any
  onChange: (v: any) => void
  path?: string
}) {
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set(['shots', 'performanceChart', 'cameraCurves', 'contactLock', 'locomotionCycles', 'transitionEdges', 'foleyTimeline', 'actingLead', 'phonemeSync', 'frameGate', 'audioTimeline', 'continuity', 'palette']))

  const toggle = (key: string) => {
    setCollapsed(prev => {
      const next = new Set(prev)
      if (next.has(key)) next.delete(key); else next.add(key)
      return next
    })
  }

  if (data === null || data === undefined) {
    return <span className="json-null">null</span>
  }

  if (typeof data === 'string') {
    return <span className="json-string">"{data}"</span>
  }

  if (typeof data === 'number') {
    return <span className="json-number">{data}</span>
  }

  if (typeof data === 'boolean') {
    return <span className="json-boolean">{data ? 'true' : 'false'}</span>
  }

  if (Array.isArray(data)) {
    if (data.length === 0) return <span className="json-bracket">[]</span>
    const key = path || 'root'
    const isCollapsed = collapsed.has(key)
    return (
      <div className="json-array">
        <span className="json-toggle" onClick={() => toggle(key)}>
          {isCollapsed ? '▶' : '▼'} [{data.length}]
        </span>
        {!isCollapsed && (
          <div className="json-children">
            {data.map((item, i) => (
              <div key={i} className="json-entry" style={{ marginLeft: 16 }}>
                <span className="json-key">{i}:</span>{' '}
                <JSONInspector data={item} onChange={onChange} path={`${path}[${i}]`} />
              </div>
            ))}
          </div>
        )}
      </div>
    )
  }

  if (typeof data === 'object') {
    const keys = Object.keys(data)
    if (keys.length === 0) return <span className="json-bracket">{'{}'}</span>
    const key = path || 'root'
    const isCollapsed = collapsed.has(key)
    return (
      <div className="json-object">
        <span className="json-toggle" onClick={() => toggle(key)}>
          {isCollapsed ? '▶' : '▼'} {'{'}...{'}'}
        </span>
        {!isCollapsed && (
          <div className="json-children">
            {keys.map(k => {
              const val = data[k]
              return (
                <div key={k} className="json-entry" style={{ marginLeft: 16 }}>
                  <span className="json-key" onClick={() => toggle(`${path}/${k}`)}>{k}:</span>{' '}
                  {typeof val === 'object' && val !== null ? (
                    <JSONInspector data={val} onChange={onChange} path={`${path}/${k}`} />
                  ) : (
                    <JSONValueDisplay value={val} />
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>
    )
  }

  return <span>{String(data)}</span>
}

function JSONValueDisplay({ value }: { value: any }) {
  if (value === null || value === undefined) return <span className="json-null">null</span>
  if (typeof value === 'string') return <span className="json-string">"{value}"</span>
  if (typeof value === 'number') return <span className="json-number">{value}</span>
  if (typeof value === 'boolean') return <span className="json-boolean">{value ? 'true' : 'false'}</span>
  return <span>{String(value)}</span>
}
