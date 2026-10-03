import { useCallback, useEffect, useState } from 'react'
import {
  approveRoute,
  deleteRoute,
  listPatients,
  listRoutes,
  saveRoute,
  sendApprovedRoute,
} from '../api/routesApi'
import ManualIntake from '../components/ManualIntake'
import PriorityBadge from '../components/PriorityBadge'
import RouteCard from '../components/RouteCard'

const APPROVED_FILTERS = [
  { value: 'pending', label: 'Ожидают проверки', approved: false },
  { value: 'approved', label: 'Подтверждены и отправлены', approved: true },
  { value: 'all', label: 'Все записи', approved: undefined },
]

function readOutbox() {
  try {
    return JSON.parse(localStorage.getItem('sparrow_client_outbox') || '[]')
  } catch {
    return []
  }
}

export default function AdminDashboard() {
  const [routes, setRoutes] = useState([])
  const [patients, setPatients] = useState([])
  const [selectedId, setSelectedId] = useState(null)
  const [draft, setDraft] = useState(null)
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [toast, setToast] = useState('')
  const [patientFilter, setPatientFilter] = useState('')
  const [approvedFilter, setApprovedFilter] = useState('pending')
  const [ingestErrors, setIngestErrors] = useState([])
  const [outbox, setOutbox] = useState(readOutbox)

  const load = useCallback(async ({ silent = false } = {}) => {
    if (!silent) setLoading(true)
    setError('')
    try {
      const filterMeta = APPROVED_FILTERS.find((f) => f.value === approvedFilter)
      const [data, pats] = await Promise.all([
        listRoutes({
          patientId: patientFilter || undefined,
          approved: filterMeta?.approved,
        }),
        listPatients(),
      ])
      setPatients(pats)
      setRoutes(data)
      setSelectedId((prev) => {
        if (prev && data.some((r) => r.id === prev)) return prev
        return data[0]?.id ?? null
      })
      setDraft((prev) => {
        const nextId = prev && data.some((r) => r.id === prev.id) ? prev.id : data[0]?.id
        const item = data.find((r) => r.id === nextId)
        return item ? { ...item } : null
      })
    } catch (err) {
      setError(`Не удалось загрузить очередь: ${err.message || err}`)
    } finally {
      if (!silent) setLoading(false)
    }
  }, [patientFilter, approvedFilter])

  const focusRoute = useCallback(async (route) => {
    const [data, pats] = await Promise.all([
      listRoutes({ approved: route.approved }),
      listPatients(),
    ])
    setPatients(pats)
    setRoutes(data)
    setPatientFilter('')
    setApprovedFilter(route.approved ? 'approved' : 'pending')
    setSelectedId(route.id)
    setDraft({ ...route })
  }, [])

  useEffect(() => {
    load()
  }, [load])

  useEffect(() => {
    const events = new EventSource('/api/v1/admin/events')
    const onRouteCreated = () => {
      load({ silent: true })
    }
    const onIngestError = (event) => {
      try {
        const received = JSON.parse(event.data)
        const notification = {
          id: received.id || event.lastEventId || `${Date.now()}-${Math.random()}`,
          ...(received.data || received),
        }
        setIngestErrors((current) =>
          current.some((item) => item.id === notification.id)
            ? current
            : [...current, notification],
        )
      } catch {
        setIngestErrors((current) => [
          ...current,
          {
            id: `${Date.now()}-${Math.random()}`,
            message: 'Получено некорректное сообщение об ошибке загрузки.',
          },
        ])
      }
    }

    events.addEventListener('route.created', onRouteCreated)
    events.addEventListener('auto_ingest.error', onIngestError)
    return () => events.close()
  }, [load])

  function select(id) {
    const item = routes.find((r) => r.id === id)
    setSelectedId(id)
    setDraft(item ? { ...item } : null)
    setToast('')
  }

  async function handleSave(route) {
    setBusy(true)
    setToast('')
    try {
      const saved = await saveRoute(route)
      setToast(`Сохранено · approved сброшен · ${saved.updatedAt}`)
      await focusRoute(saved)
    } catch (err) {
      setToast(`Ошибка сохранения: ${err.message || err}`)
    } finally {
      setBusy(false)
    }
  }

  async function handleApprove() {
    if (!draft) return
    setBusy(true)
    setToast('')
    try {
      const saved = await approveRoute(draft.id)
      try {
        const receipt = sendApprovedRoute(saved)
        setOutbox(readOutbox())
        setToast(`Подтверждено и передано клиенту (заглушка) · ${receipt.routeId}`)
      } catch (deliveryError) {
        setToast(`Подтверждено · ошибка заглушки доставки: ${deliveryError.message || deliveryError}`)
      }
      await focusRoute(saved)
    } catch (err) {
      setToast(`Ошибка approve: ${err.message || err}`)
    } finally {
      setBusy(false)
    }
  }

  async function handleManualSubmitted(route) {
    setToast('')
    await focusRoute(route)
  }

  async function handleDelete() {
    if (!draft) return
    if (!window.confirm(`Удалить запись ${draft.id}?`)) return
    setBusy(true)
    setToast('')
    try {
      await deleteRoute(draft.id)
      setToast(`Удалено · ${draft.id}`)
      await load()
    } catch (err) {
      setToast(`Ошибка удаления: ${err.message || err}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="page">
      {ingestErrors.length > 0 && (
        <section className="ingest-alert-stack" aria-label="Ошибки автоматической загрузки" aria-live="assertive">
          {ingestErrors.map((item) => (
            <article className="ingest-alert" role="alert" key={item.id}>
              <div className="ingest-alert-copy">
                <strong>Обследование не загружено</strong>
                <p>{item.message || 'Источник сообщил об ошибке автоматической загрузки.'}</p>
                {(item.patient_name || item.patient_id || item.filename || item.exam_id) && (
                  <small>
                    {[item.patient_name, item.patient_id, item.filename, item.exam_id]
                      .filter(Boolean)
                      .join(' · ')}
                  </small>
                )}
              </div>
              <button
                type="button"
                className="ingest-alert-dismiss"
                aria-label="Закрыть уведомление"
                onClick={() => setIngestErrors((current) => current.filter((error) => error.id !== item.id))}
              >
                Закрыть
              </button>
            </article>
          ))}
        </section>
      )}
      <header className="page-head">
        <h1>Проверка результатов</h1>
        <p className="lede">Результаты обследований обрабатываются сервером и попадают сюда на проверку.</p>
      </header>

      <ManualIntake onSubmitted={handleManualSubmitted} />

      <section className="panel filters-bar">
        <label className="field">
          <span>Пациент</span>
          <select value={patientFilter} onChange={(e) => setPatientFilter(e.target.value)}>
            <option value="">Все пациенты</option>
            {patients.map((p) => (
              <option key={p.patientId} value={p.patientId}>
                {p.patientName} ({p.patientId})
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Статус</span>
          <select value={approvedFilter} onChange={(e) => setApprovedFilter(e.target.value)}>
            {APPROVED_FILTERS.map((f) => (
              <option key={f.value} value={f.value}>
                {f.label}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="btn ghost" disabled={loading || busy} onClick={() => load()}>
          Обновить
        </button>
      </section>

      {loading ? (
        <p className="muted">Загрузка очереди…</p>
      ) : error ? (
        <p className="error">{error}</p>
      ) : (
        <div className="split admin-split">
          <section className="panel list-panel">
            <h2>
              {approvedFilter === 'pending' ? 'Ожидают проверки' : 'Результаты'} ({routes.length})
            </h2>
            {routes.length === 0 ? (
              <p className="empty">Нет записей по фильтру</p>
            ) : (
              <ul className="route-list">
                {routes.map((r) => (
                  <li key={r.id}>
                    <button
                      type="button"
                      className={`route-list-item ${selectedId === r.id ? 'active' : ''}`}
                      onClick={() => select(r.id)}
                    >
                      <div className="route-list-top">
                        <strong>{r.patientName}</strong>
                        <PriorityBadge priority={r.priority} />
                      </div>
                    <span className="muted">
                      {r.patientId} · {(r.documents || []).length} док. ·{' '}
                      {r.approved ? 'отправлено клиенту' : 'ожидает проверки'}
                    </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="panel">
            <h2>Карточка</h2>
            {draft ? (
              <>
                <p className="hint" style={{ marginBottom: '0.75rem' }}>
                  {draft.approved ? (
                    <span className="pill">отправлено клиенту</span>
                  ) : (
                    <span className="pill pill-warn">ожидает проверки</span>
                  )}{' '}
                  · {draft.patientId}
                </p>
                <RouteCard
                  route={draft}
                  editable
                  onChange={setDraft}
                  onSave={handleSave}
                  saving={busy}
                />
                <div className="actions admin-actions">
                  <button
                    type="button"
                    className="btn approve"
                    disabled={busy || draft.approved}
                    onClick={handleApprove}
                  >
                    Подтвердить и отправить
                  </button>
                  <button type="button" className="btn danger" disabled={busy} onClick={handleDelete}>
                    Удалить
                  </button>
                </div>
                {toast && <p className="hint">{toast}</p>}
              </>
            ) : (
              <p className="empty">Выберите карточку слева</p>
            )}
          </section>
        </div>
      )}

      <section className="panel outbox-panel">
        <div className="intake-heading">
          <div>
            <p className="eyebrow">Канал доставки · заглушка</p>
            <h2>Передано клиентам</h2>
          </div>
          <span className="pill">{outbox.length}</span>
        </div>
        {outbox.length ? (
          <ul className="outbox-list">
            {outbox.slice().reverse().map((item) => (
              <li key={item.routeId}>
                <strong>{item.patientName}</strong>
                <span className="muted">{item.patientId} · {item.routeId}</span>
                <time className="muted" dateTime={item.sentAt}>
                  {new Date(item.sentAt).toLocaleString()}
                </time>
              </li>
            ))}
          </ul>
        ) : (
          <p className="empty">Подтверждённые результаты появятся здесь.</p>
        )}
      </section>
    </div>
  )
}
