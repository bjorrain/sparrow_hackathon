function TokenChips({ items, tone = "default" }) {
  if (!items?.length) return <span className="muted">—</span>
  return (
    <div className="chip-row">
      {items.map((item, i) => (
        <span key={`${item}-${i}`} className={`chip chip-${tone}`}>
          {item}
        </span>
      ))}
    </div>
  )
}

function ImportantBlock({ important }) {
  const i = important || {}
  const labs = i.labs || []
  const vitals = Object.entries(i.vitals || {})

  return (
    <div className="token-grid">
      {(i.patient_name || i.age != null || i.sex) && (
        <div className="token-field">
          <span className="token-label">Пациент</span>
          <strong>
            {[i.patient_name, i.age != null ? `${i.age} лет` : null, i.sex]
              .filter(Boolean)
              .join(' · ') || '—'}
          </strong>
        </div>
      )}
      <div className="token-field">
        <span className="token-label">Red flags</span>
        <TokenChips items={i.red_flags} tone="danger" />
      </div>
      <div className="token-field">
        <span className="token-label">Симптомы</span>
        <TokenChips items={i.symptoms} tone="warn" />
      </div>
      <div className="token-field">
        <span className="token-label">Диагнозы</span>
        <TokenChips items={i.diagnoses} />
      </div>
      <div className="token-field">
        <span className="token-label">Labs</span>
        {labs.length ? (
          <ul className="lab-list">
            {labs.map((lab, idx) => (
              <li key={idx}>
                <strong>{lab.name}</strong>: {lab.value}
                {lab.unit ? ` ${lab.unit}` : ''}
                {lab.ref_range ? ` (ref ${lab.ref_range})` : ''}
              </li>
            ))}
          </ul>
        ) : (
          <span className="muted">—</span>
        )}
      </div>
      <div className="token-field">
        <span className="token-label">Vitals</span>
        {vitals.length ? (
          <TokenChips items={vitals.map(([k, v]) => `${k}: ${v}`)} />
        ) : (
          <span className="muted">—</span>
        )}
      </div>
      <div className="token-field">
        <span className="token-label">Медикаменты</span>
        <TokenChips items={i.medications} />
      </div>
      <div className="token-field wide">
        <span className="token-label">Clinical snippets</span>
        {(i.clinical_snippets || []).length ? (
          <ul className="snippet-list">
            {i.clinical_snippets.map((s, idx) => (
              <li key={idx}>«{s}»</li>
            ))}
          </ul>
        ) : (
          <span className="muted">—</span>
        )}
      </div>
    </div>
  )
}

function JunkBlock({ junk }) {
  const j = junk || {}
  const groups = [
    ['Шапка / футер', j.headers_footers],
    ['Клиника / контакты', j.clinic_meta],
    ['ID документов', j.document_ids],
    ['Legalese', j.legalese],
    ['Прочий шум', j.other_noise],
  ].filter(([, items]) => items?.length)

  if (!groups.length) return <p className="muted">Мусора не выделено</p>

  return (
    <div className="junk-grid">
      {groups.map(([label, items]) => (
        <div key={label} className="token-field">
          <span className="token-label">{label}</span>
          <ul className="snippet-list muted-list">
            {items.map((item, idx) => (
              <li key={idx}>{item}</li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  )
}

function hasContent(value) {
  if (Array.isArray(value)) return value.length > 0
  if (value && typeof value === 'object') return Object.keys(value).length > 0
  return value !== null && value !== undefined && value !== ''
}

function DataValue({ value }) {
  if (!hasContent(value)) return <span className="muted">—</span>
  if (Array.isArray(value)) {
    return (
      <ul className="structured-value-list">
        {value.map((item, index) => (
          <li key={index}><DataValue value={item} /></li>
        ))}
      </ul>
    )
  }
  if (typeof value === 'object') {
    return (
      <dl className="structured-data-list">
        {Object.entries(value).map(([key, item]) => (
          <div key={key}>
            <dt>{key.replaceAll('_', ' ')}</dt>
            <dd><DataValue value={item} /></dd>
          </div>
        ))}
      </dl>
    )
  }
  return <>{String(value)}</>
}

function StructuredReport({ document }) {
  const structures = document.structures || []
  const technicalData = document.technicalData || document.technical_data || {}
  const conclusion = document.conclusion || {}
  const hasTechnicalData = hasContent(technicalData)
  const hasConclusion = hasContent(conclusion)

  if (!structures.length && !hasTechnicalData && !hasConclusion) return null

  return (
    <section className="structured-report">
      {structures.length > 0 && (
        <>
          <h4 className="doc-section-title">Структуры</h4>
          <div className="structures-list">
            {structures.map((structure, index) => {
              const status = structure.status || ''
              const statusTone = /патолог|измен/i.test(status) ? 'pathology' : 'normal'
              const morphology = structure.morphology || {}
              return (
                <article className="structure-item" key={`${structure.name || 'structure'}-${index}`}>
                  <div className="structure-heading">
                    <strong>{structure.name || `Структура ${index + 1}`}</strong>
                    {status && <span className={`structure-status ${statusTone}`}>{status}</span>}
                  </div>
                  {hasContent(structure.size) && (
                    <div className="structure-field">
                      <span>Размеры / описание</span>
                      <DataValue value={structure.size} />
                    </div>
                  )}
                  {hasContent(morphology) && (
                    <div className="structure-morphology">
                      {Object.entries(morphology).map(([key, value]) => (
                        <div className="structure-field" key={key}>
                          <span>{key.replaceAll('_', ' ')}</span>
                          <DataValue value={value} />
                        </div>
                      ))}
                    </div>
                  )}
                </article>
              )
            })}
          </div>
        </>
      )}

      {hasTechnicalData && (
        <>
          <h4 className="doc-section-title">Технические данные</h4>
          <DataValue value={technicalData} />
        </>
      )}

      {hasConclusion && (
        <>
          <h4 className="doc-section-title">Заключение</h4>
          <div className="conclusion-block">
            {conclusion.text && (
              <div className="structure-field">
                <span>Текст</span>
                <DataValue value={conclusion.text} />
              </div>
            )}
            {conclusion.recommendations && (
              <div className="structure-field">
                <span>Рекомендации</span>
                <DataValue value={conclusion.recommendations} />
              </div>
            )}
            {!conclusion.text && !conclusion.recommendations && <DataValue value={conclusion} />}
          </div>
        </>
      )}
    </section>
  )
}

export default function DocumentsPanel({ documents = [], collapsible = true }) {
  if (!documents.length) {
    return <p className="empty">Документов в тикете нет</p>
  }

  return (
    <div className="docs-stack">
      {documents.map((doc, index) => (
        <details key={doc.id || index} className="doc-card" open={index === 0 || !collapsible}>
          <summary className="doc-summary">
            <span className="doc-index">#{index + 1}</span>
            <span className="doc-name">{doc.filename || 'document'}</span>
            <span className="pill">{doc.filetype || 'text'}</span>
            {doc.structureModel || doc.structure_model ? (
              <span className="muted doc-model">
                {doc.structureModel || doc.structure_model}
              </span>
            ) : null}
          </summary>

          {doc.summary ? <p className="doc-summary-text">{doc.summary}</p> : null}

          <StructuredReport document={doc} />

          {Object.values(doc.important || {}).some(hasContent) && (
            <>
              <h4 className="doc-section-title">Важные данные</h4>
              <ImportantBlock important={doc.important} />
            </>
          )}

          {doc.tokenMeta?.active_features?.length || doc.tokenMeta?.token_filter?.dropped?.length ? (
            <>
              <h4 className="doc-section-title">Token filter</h4>
              {doc.tokenMeta.active_features?.length ? (
                <div className="token-field">
                  <span className="token-label">Active features</span>
                  <TokenChips items={doc.tokenMeta.active_features} tone="warn" />
                </div>
              ) : null}
              {doc.tokenMeta.token_filter?.dropped?.length ? (
                <div className="token-field">
                  <span className="token-label">Dropped (норма / отрицание)</span>
                  <TokenChips
                    items={doc.tokenMeta.token_filter.dropped.map(
                      (d) => d.token || d.reason || '—',
                    )}
                  />
                </div>
              ) : null}
            </>
          ) : null}

          {Object.values(doc.metadataJunk || doc.metadata_junk || {}).some(hasContent) && (
            <>
              <h4 className="doc-section-title">Метаданные</h4>
              <JunkBlock junk={doc.metadataJunk || doc.metadata_junk} />
            </>
          )}

          {doc.rawText || doc.raw_text ? (
            <>
              <h4 className="doc-section-title">Raw text</h4>
              <pre className="raw-pre">{doc.rawText || doc.raw_text}</pre>
            </>
          ) : null}
        </details>
      ))}
    </div>
  )
}
