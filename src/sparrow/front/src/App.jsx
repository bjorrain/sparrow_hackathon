import { useState } from 'react'
import { extractClinicalFindings } from './api/clinicalApi'

const EXAMPLE_TEXT = `Артерии правой и левой стороны проходимы. В правом яичнике определяется образование 22х18 мм с ровными контурами. В области шейки матки отмечается деформация. Заключение: УЗ-признаки кистозного образования. Рекомендована срочная консультация.`

const STATUS_CLASSNAMES = {
  норма: 'status-normal',
  изменение: 'status-change',
  патология: 'status-pathology',
}

const URGENCY_CLASSNAMES = {
  норма: 'urgency-normal',
  планово: 'urgency-routine',
  срочно: 'urgency-soon',
  неотложно: 'urgency-emergency',
}

function renderStructuredValue(value, depth = 0) {
  if (value == null) return <span className="value-empty">—</span>

  if (Array.isArray(value)) {
    return (
      <ul className="value-list">
        {value.map((item, index) => (
          <li key={`${depth}-${index}`}>{renderStructuredValue(item, depth + 1)}</li>
        ))}
      </ul>
    )
  }

  if (typeof value === 'object') {
    return (
      <div className="nested-block">
        {Object.entries(value).map(([key, item]) => (
          <div key={key} className="nested-row">
            <div className="nested-key">{key}</div>
            <div className="nested-value">{renderStructuredValue(item, depth + 1)}</div>
          </div>
        ))}
      </div>
    )
  }

  return <span className="value-plain">{String(value)}</span>
}

export default function App() {
  const [text, setText] = useState(EXAMPLE_TEXT)
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  async function handleSubmit(event) {
    event.preventDefault()
    const trimmed = text.trim()
    if (!trimmed) {
      setError('Введите текст описания или пример, чтобы выполнить анализ.')
      return
    }

    setLoading(true)
    setError('')

    try {
      const payload = await extractClinicalFindings(trimmed)
      setResult(payload)
    } catch (err) {
      setError(err.message || 'Не удалось выполнить анализ.')
    } finally {
      setLoading(false)
    }
  }

  const structuredData = result?.structured_data || {}
  const serviceInfo = structuredData['служебная_информация'] || {}
  const structures = structuredData['структуры'] || {}
  const sides = structuredData['стороны'] || {}

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand" aria-label="Sparrow clinical parser">
          <span className="brand-mark">Sparrow</span>
          <span className="brand-sub">Clinical parser</span>
        </div>
        <div className="topbar-meta">
          <span className="pill">FastAPI /extract</span>
        </div>
      </header>

      <main className="main">
        <section className="page-head">
          <h1>Разбор клинических описаний</h1>
          <p className="lede">
            Вставьте текст протокола, и сервер извлечёт фрагменты, оценит статус и срочность,
            а также вернёт структурированные данные по органам и сторонам.
          </p>
        </section>

        <div className="clinical-layout">
          <section className="panel clinical-panel">
            <div className="intake-heading">
              <div>
                <p className="eyebrow">Ввод</p>
                <h2>Описание обследования</h2>
              </div>
            </div>

            <form onSubmit={handleSubmit}>
              <label className="field">
                <span>Текст</span>
                <textarea
                  value={text}
                  onChange={(event) => setText(event.target.value)}
                  placeholder="Вставьте описание обследования..."
                  aria-label="Текст описания обследования"
                />
              </label>

              <div className="actions">
                <button type="submit" className="btn primary" disabled={loading}>
                  {loading ? 'Анализ…' : 'Извлечь находки'}
                </button>
                <button
                  type="button"
                  className="btn ghost"
                  onClick={() => setText(EXAMPLE_TEXT)}
                >
                  Пример
                </button>
              </div>

              {error && <p className="error">{error}</p>}
            </form>
          </section>

          <section className="panel results-panel">
            {!result ? (
              <div className="empty">
                Здесь появятся найденные фрагменты, статус, срочность и структурированная
                информация по протоколу.
              </div>
            ) : (
              <>
                <div className="results-header">
                  <div>
                    <p className="eyebrow">Результат</p>
                    <h2>Выявленные находки</h2>
                  </div>
                </div>

                <div className="findings-list">
                  {result.findings?.length ? (
                    result.findings.map((finding, index) => (
                      <article className="finding-card" key={`${finding.summary}-${index}`}>
                        <div className="finding-header">
                          <span className={`status-badge ${STATUS_CLASSNAMES[finding.status] || ''}`}>
                            {finding.status}
                          </span>
                          <span className={`urgency-badge ${URGENCY_CLASSNAMES[finding.urgency] || ''}`}>
                            {finding.urgency}
                          </span>
                        </div>
                        <p>{finding.summary}</p>
                      </article>
                    ))
                  ) : (
                    <p className="empty">Ничего не найдено.</p>
                  )}
                </div>

                <div className="structured-section">
                  <h3>Структурированные данные</h3>

                  {Object.keys(serviceInfo).length > 0 && (
                    <div className="meta-card">
                      <h4>Служебная информация</h4>
                      {renderStructuredValue(serviceInfo)}
                    </div>
                  )}

                  {Object.keys(structures).length > 0 && (
                    <div className="meta-card">
                      <h4>Структуры</h4>
                      {renderStructuredValue(structures)}
                    </div>
                  )}

                  {Object.keys(sides).length > 0 && (
                    <div className="meta-card">
                      <h4>Стороны</h4>
                      {renderStructuredValue(sides)}
                    </div>
                  )}

                  {structuredData['прочие_находки']?.length > 0 && (
                    <div className="meta-card">
                      <h4>Прочие находки</h4>
                      <ul className="value-list">
                        {structuredData['прочие_находки'].map((item, index) => (
                          <li key={`${item}-${index}`}>{item}</li>
                        ))}
                      </ul>
                    </div>
                  )}

                  {structuredData['заключение'] && (
                    <div className="meta-card">
                      <h4>Заключение</h4>
                      <p>{structuredData['заключение']}</p>
                    </div>
                  )}

                  {structuredData['рекомендации'] && (
                    <div className="meta-card">
                      <h4>Рекомендации</h4>
                      <p>{structuredData['рекомендации']}</p>
                    </div>
                  )}
                </div>
              </>
            )}
          </section>
        </div>
      </main>
    </div>
  )
}
