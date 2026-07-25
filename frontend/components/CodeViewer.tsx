import { useState } from 'react'

type CodeFile = {
  label: string
  content: string
  language?: string
}

export default function CodeViewer({ files }: { files: CodeFile[] }) {
  const [activeIndex, setActiveIndex] = useState(0)
  const [copied, setCopied] = useState(false)

  if (!files || files.length === 0) return null

  const active = files[activeIndex]
  const lines = active.content.split('\n')

  const handleCopy = async () => {
    await navigator.clipboard.writeText(active.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleDownload = () => {
    const ext = active.language === 'typescript' ? '.ts' :
                active.language === 'javascript' ? '.js' :
                active.language === 'python' ? '.py' :
                active.language === 'bash' ? '.sh' : '.txt'
    const filename = active.label.replace(/[^a-zA-Z0-9_.-]/g, '_') + ext
    const blob = new Blob([active.content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleDownloadAll = () => {
    const zipBlob = new Blob(
      files.map(f => new Blob([f.label + '\n' + '-'.repeat(40) + '\n' + f.content + '\n\n'])),
      { type: 'text/plain' }
    )
    const url = URL.createObjectURL(zipBlob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'remotion-project.zip'
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="code-viewer">
      <div className="code-viewer-tabs">
        {files.map((f, i) => (
          <button
            key={i}
            className={`tab ${i === activeIndex ? 'active' : ''}`}
            onClick={() => setActiveIndex(i)}
          >
            {f.label}
          </button>
        ))}
        <div className="code-viewer-actions">
          <button className="action-btn" onClick={handleCopy} title="کپی">
            {copied ? '✓ کپی شد' : '📋 کپی'}
          </button>
          <button className="action-btn" onClick={handleDownload} title="دانلود فایل">
            ⬇ دانلود
          </button>
          {files.length > 1 && (
            <button className="action-btn" onClick={handleDownloadAll} title="دانلود همه">
              📦 همه
            </button>
          )}
        </div>
      </div>
      <div className="code-viewer-body">
        <table className="code-table">
          <tbody>
            {lines.map((line, i) => (
              <tr key={i} className="code-line">
                <td className="line-number">{i + 1}</td>
                <td className="line-content" dir="ltr">
                  <HighlightedCode code={line} language={active.language} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function HighlightedCode({ code, language }: { code: string; language?: string }) {
  if (language === 'typescript' || language === 'javascript') {
    return <span dangerouslySetInnerHTML={{ __html: highlightTS(code) }} />
  }
  if (language === 'python') {
    return <span dangerouslySetInnerHTML={{ __html: highlightPython(code) }} />
  }
  if (language === 'bash' || language === 'shell') {
    return <span dangerouslySetInnerHTML={{ __html: highlightBash(code) }} />
  }
  return <span>{code}</span>
}

function escapeHtml(s: string): string {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

function highlightTS(code: string): string {
  return escapeHtml(code)
    .replace(/(\/\/[^"]*?)$/gm, '<span class="hl-comment">$1</span>')
    .replace(/\b(import|export|from|const|let|var|function|return|if|else|for|while|async|await|type|interface|extends|implements|new|this|class|default|as|of|in|keyof|typeof)\b/g, '<span class="hl-keyword">$1</span>')
    .replace(/"([^"]*)"/g, '<span class="hl-string">"$1"</span>')
    .replace(/'([^']*)'/g, "<span class='hl-string'>'$1'</span>")
    .replace(/\b(\d+\.?\d*)\b/g, '<span class="hl-number">$1</span>')
    .replace(/(\/\/\s*TODO:?[\s\S]*?)$/gm, '<span class="hl-todo">$1</span>')
}

function highlightPython(code: string): string {
  return escapeHtml(code)
    .replace(/(#.*?)$/gm, '<span class="hl-comment">$1</span>')
    .replace(/\b(import|from|def|class|return|if|elif|else|for|while|async|await|with|as|in|not|and|or|True|False|None|self|yield|lambda|pass|raise|try|except|finally)\b/g, '<span class="hl-keyword">$1</span>')
    .replace(/"([^"]*)"/g, '<span class="hl-string">"$1"</span>')
    .replace(/'([^']*)'/g, "<span class='hl-string'>'$1'</span>")
    .replace(/\b(\d+\.?\d*)\b/g, '<span class="hl-number">$1</span>')
}

function highlightBash(code: string): string {
  return escapeHtml(code)
    .replace(/(#.*?)$/gm, '<span class="hl-comment">$1</span>')
    .replace(/\b(export|source|if|then|else|fi|for|do|done|while|function|return|local|exit|echo|cd|mkdir|cp|mv|rm|npm|npx|node|python|pip)\b/g, '<span class="hl-keyword">$1</span>')
    .replace(/"([^"]*)"/g, '<span class="hl-string">"$1"</span>')
    .replace(/'([^']*)'/g, "<span class='hl-string'>'$1'</span>")
}
