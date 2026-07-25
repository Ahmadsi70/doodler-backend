import { useState } from 'react'

type Shot = Record<string, any>
type StoryProps = Record<string, any>

const TEXT_FIELDS = ['action', 'dialogue', 'verb', 'storyBeat', 'composition', 'shotSize', 'lookSpace']
const NUMERIC_FIELDS = ['durationSec', 'durationFrames', 'holdFrames', 'anticipationFrames', 'thirdsX', 'shotSizeScale']
const CHOICE_FIELDS: Record<string, string[]> = {
  lens: ['standard', 'wide', 'telephoto', 'fisheye', 'macro', 'anamorphic'],
  camera: ['static', 'pan', 'tilt', 'dolly', 'track', 'crane', 'aerial'],
  lighting: ['three_point', 'rim', 'practical', 'natural', 'hard', 'soft', 'moody', 'silhouette'],
  shotSize: ['ECU', 'CU', 'MCU', 'MS', 'MLS', 'LS', 'ELS'],
  cameraMove: ['static', 'pan_left', 'pan_right', 'tilt_up', 'tilt_down', 'dolly_in', 'dolly_out', 'track_left', 'track_right', 'crane_up', 'crane_down'],
}

export default function ShotEditor({
  shot,
  shotIndex,
  isSelected,
  onSelect,
  allProps,
  onPropsChange,
}: {
  shot: Shot
  shotIndex: number
  isSelected: boolean
  onSelect: () => void
  allProps: StoryProps
  onPropsChange: (p: StoryProps) => void
}) {
  const [expanded, setExpanded] = useState(isSelected)
  const [editMode, setEditMode] = useState(false)
  const [localShot, setLocalShot] = useState<Shot>({ ...shot })

  const sid = shot.shotId ?? shotIndex
  const keyframes: any[] = shot.shotRig?.keyframes || []
  const cameraCurve: any[] = shot.cameraCurve?.keyframes || []

  const updateShotProp = (key: string, value: any) => {
    const updated = { ...localShot, [key]: value }
    setLocalShot(updated)
  }

  const saveChanges = () => {
    const newShots = [...(allProps.shots || [])]
    newShots[shotIndex] = { ...localShot }
    onPropsChange({ ...allProps, shots: newShots })
    setEditMode(false)
  }

  const revertChanges = () => {
    setLocalShot({ ...shot })
    setEditMode(false)
  }

  return (
    <div className={`shot-editor ${isSelected ? 'selected' : ''}`}>
      <div className="shot-editor-header" onClick={() => { onSelect(); setExpanded(!expanded) }}>
        <div className="shot-editor-title">
          <span className="shot-editor-id">#{sid}</span>
          <span className="shot-editor-action">{shot.action || 'بدون توضیح'}</span>
        </div>
        <div className="shot-editor-meta">
          <span className="shot-badge">{shot.shotSize || 'MS'}</span>
          <span className="shot-badge">{shot.durationSec || 3}s</span>
          <span className="shot-badge">{shot.camera || 'static'}</span>
          <span className="shot-badge">{shot.lens || 'standard'}</span>
          {expanded ? '▲' : '▼'}
        </div>
      </div>

      {expanded && (
        <div className="shot-editor-body">
          {!editMode ? (
            <div className="shot-editor-view">
              <PropertyTable shot={shot} />
              {keyframes.length > 0 && <KeyframeViewer keyframes={keyframes} title="شات ریگ" />}
              {cameraCurve.length > 0 && <KeyframeViewer keyframes={cameraCurve} title="منحنی دوربین" />}
              <div className="shot-editor-actions">
                <button className="editor-btn" onClick={() => setEditMode(true)}>✏️ ویرایش</button>
              </div>
            </div>
          ) : (
            <div className="shot-editor-edit">
              {Object.keys(localShot).filter(k => !['shotRig', 'cameraCurve', 'envProfile', 'craftHints', 'transitionIn'].includes(k)).map(key => {
                const val = localShot[key]
                const choices = CHOICE_FIELDS[key]

                if (choices) {
                  return (
                    <div key={key} className="field-row">
                      <label>{key}</label>
                      <select value={val || ''} onChange={e => updateShotProp(key, e.target.value)}>
                        {choices.map(c => <option key={c} value={c}>{c}</option>)}
                      </select>
                    </div>
                  )
                }

                if (TEXT_FIELDS.includes(key)) {
                  return (
                    <div key={key} className="field-row">
                      <label>{key}</label>
                      <input type="text" value={val || ''} onChange={e => updateShotProp(key, e.target.value)} />
                    </div>
                  )
                }

                if (NUMERIC_FIELDS.includes(key)) {
                  return (
                    <div key={key} className="field-row">
                      <label>{key}</label>
                      <input type="number" step="0.1" value={val ?? ''} onChange={e => updateShotProp(key, parseFloat(e.target.value) || 0)} />
                    </div>
                  )
                }

                if (Array.isArray(val) || (typeof val === 'object' && val !== null)) {
                  return null
                }

                return (
                  <div key={key} className="field-row">
                    <label>{key}</label>
                    <input type="text" value={String(val ?? '')} onChange={e => updateShotProp(key, e.target.value)} />
                  </div>
                )
              })}

              <div className="shot-editor-edit-actions">
                <button className="editor-btn primary" onClick={saveChanges}>💾 ذخیره</button>
                <button className="editor-btn" onClick={revertChanges}>↩️ بازگشت</button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function PropertyTable({ shot }: { shot: Shot }) {
  const displayKeys = ['action', 'durationSec', 'durationFrames', 'holdFrames', 'anticipationFrames', 'shotSize', 'camera', 'lens', 'lighting', 'composition', 'shotSizeScale', 'thirdsX', 'lookSpace', 'storyBeat', 'verb', 'dialogue']
  return (
    <table className="props-table">
      <tbody>
        {displayKeys.map(key => {
          if (key in shot) {
            return (
              <tr key={key}>
                <td className="props-key">{key}</td>
                <td className="props-val">{typeof shot[key] === 'object' ? JSON.stringify(shot[key]) : String(shot[key] ?? '')}</td>
              </tr>
            )
          }
          return null
        })}
      </tbody>
    </table>
  )
}

function KeyframeViewer({ keyframes, title }: { keyframes: any[]; title: string }) {
  const [expanded, setExpanded] = useState(false)

  if (keyframes.length === 0) return null

  const jointKeys = Object.keys(keyframes[0]?.joints || {})
  const hasJointData = jointKeys.length > 0

  return (
    <div className="keyframe-viewer">
      <div className="keyframe-viewer-header" onClick={() => setExpanded(!expanded)}>
        <span>{title} ({keyframes.length} keyframe{keyframes.length > 1 ? 's' : ''})</span>
        <span>{expanded ? '▲' : '▼'}</span>
      </div>
      {expanded && (
        <div className="keyframe-viewer-body">
          {hasJointData ? (
            <table className="kf-table">
              <thead>
                <tr>
                  <th>Frame</th>
                  <th>Phase</th>
                  {jointKeys.slice(0, 6).map(jk => <th key={jk}>{jk}</th>)}
                </tr>
              </thead>
              <tbody>
                {keyframes.map((kf, i) => (
                  <tr key={i}>
                    <td>{kf.frame}</td>
                    <td>{kf.phase || '-'}</td>
                    {jointKeys.slice(0, 6).map(jk => (
                      <td key={jk}>{(kf.joints?.[jk] ?? '-').toFixed(3)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <div className="kf-grid">
              {keyframes.map((kf, i) => (
                <div key={i} className="kf-card">
                  <strong>Frame {kf.frame}</strong>
                  {kf.phase && <span> ({kf.phase})</span>}
                  <code>{JSON.stringify(Object.fromEntries(Object.entries(kf).filter(([k]) => k !== 'frame' && k !== 'phase')))}</code>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
