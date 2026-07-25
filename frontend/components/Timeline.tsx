import { useMemo } from 'react'

type Shot = {
  shotId?: number
  title?: string
  action?: string
  durationSec?: number
  durationFrames?: number
  holdFrames?: number
  anticipationFrames?: number
  shotSize?: string
  camera?: string
  lens?: string
  lighting?: string
  storyBeat?: string
  composition?: string
  [key: string]: any
}

const SHOT_COLORS = [
  '#4c6ef5', '#7950f2', '#e64980', '#f76707',
  '#40c057', '#15aabf', '#fab005', '#fd7e14',
  '#be4bdb', '#20c997', '#339af0', '#ff6b6b',
]

function getShotColor(index: number): string {
  return SHOT_COLORS[index % SHOT_COLORS.length]
}

function formatTime(seconds: number): string {
  const m = Math.floor(seconds / 60)
  const s = Math.floor(seconds % 60)
  const ms = Math.round((seconds % 1) * 10)
  return `${m}:${s.toString().padStart(2, '0')}.${ms}`
}

export default function Timeline({
  shots,
  fps,
  selectedShot,
  onSelectShot,
}: {
  shots: Shot[]
  fps: number
  selectedShot: number | null
  onSelectShot: (id: number) => void
}) {
  const totalDuration = useMemo(
    () => shots.reduce((sum, s) => sum + (s.durationSec || 3), 0),
    [shots]
  )

  if (shots.length === 0) {
    return <div className="timeline-empty">هیچ شاتی وجود ندارد</div>
  }

  const minBarWidth = 60

  return (
    <div className="timeline-container">
      <div className="timeline-header">
        <span>{shots.length} شات</span>
        <span>{totalDuration.toFixed(1)}s @ {fps}fps</span>
      </div>

      <div className="timeline-bars">
        {shots.map((shot, i) => {
          const sid = shot.shotId ?? i
          const dur = shot.durationSec || 3
          const pct = (dur / totalDuration) * 100
          const isSelected = selectedShot === sid
          const color = getShotColor(i)

          return (
            <div
              key={sid}
              className={`timeline-bar-wrapper ${isSelected ? 'selected' : ''}`}
              style={{ width: `max(${pct}%, ${minBarWidth}px)` }}
              onClick={() => onSelectShot(sid)}
              title={`${shot.title || `Shot ${sid}`}: ${shot.action || ''}`}
            >
              <div
                className="timeline-bar"
                style={{
                  backgroundColor: color,
                  opacity: isSelected ? 1 : 0.7,
                }}
              >
                <span className="timeline-bar-label">
                  {sid}: {shot.shotSize || 'MS'}
                </span>
              </div>
              <div className="timeline-bar-duration">
                {formatTime(dur)} | {shot.durationFrames || Math.round(dur * fps)}f
              </div>
            </div>
          )
        })}
      </div>

      <div className="timeline-legend">
        {shots.map((shot, i) => {
          const sid = shot.shotId ?? i
          const color = getShotColor(i)
          return (
            <div
              key={sid}
              className="timeline-legend-item"
              onClick={() => onSelectShot(sid)}
            >
              <span className="timeline-legend-dot" style={{ backgroundColor: color }} />
              <span>{sid}: {shot.action?.slice(0, 40) || '...'}</span>
            </div>
          )
        })}
      </div>
    </div>
  )
}
