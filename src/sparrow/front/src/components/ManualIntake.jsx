import { useRef, useState } from 'react'
import { processDocument, routePatient, tokenizeText } from '../api/routesApi'

function makeTextDocument(text, tokenized) {
  return {
    id: `doc-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`,
    filename: 'manual-exam.txt',
    filetype: 'text',
    rawText: text,
    important: {
      ...(tokenized.important || {}),
      clinical_snippets: tokenized.text_tokens || [],
    },
    metadataJunk: {},
    summary: '',
    structureModel: tokenized.token_filter?.model || null,
    warnings: [],
  }
}

export default function ManualIntake({ onSubmitted }) {
  const fileRef = useRef(null)
  const [patientId, setPatientId] = useState('')
  const [patientName, setPatientName] = useState('')
  const [age, setAge] = useState('')
  const [text, setText] = useState('')
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')

  async function submit(event) {
    event.preventDefault()
    const files = Array.from(fileRef.current?.files || [])
    const examText = text.trim()
    if (!patientId.trim() || !patientName.trim()) {
      setError('Укажите идентификатор и имя пациента.')
      return
    }
    if (!files.length && !examText) {
      setError('Добавьте файл обследования или вставьте его текст.')
      return
    }

    setBusy(true)
    setError('')
    setStatus('Подготовка обследования…')
    try {
      const documents = []
      for (const file of files) {
        setStatus(`Обработка файла: ${file.name}`)
        const result = await processDocument(file)
        documents.push(result.document)
      }
      if (examText) {
        setStatus('Обработка текста обследования…')
        const tokenized = await tokenizeText(examText)
        documents.push(makeTextDocument(examText, tokenized))
      }

      setStatus('Передача данных на серверную маршрутизацию…')
      const route = await routePatient({
        documents,
        patientId: patientId.trim(),
        patientName: patientName.trim(),
        age: age ? Number(age) : null,
        sourceFile: files.map((file) => file.name).join(', ') || 'manual-exam.txt',
      })
      setStatus(`Результат ${route.id} отправлен на проверку.`)
      setText('')
      setAge('')
      if (fileRef.current) fileRef.current.value = ''
      await onSubmitted?.(route)
    } catch (err) {
      setError(`Не удалось обработать обследование: ${err.message || err}`)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="panel intake-panel">
      <div className="intake-heading">
        <div>
          <p className="eyebrow">Ручной приём</p>
          <h2>Добавить обследование</h2>
        </div>
        <span className="pill pill-warn">Если автозагрузка не сработала</span>
      </div>
      <form onSubmit={submit}>
        <div className="intake-grid">
          <label className="field">
            <span>ID пациента</span>
            <input value={patientId} onChange={(event) => setPatientId(event.target.value)} required />
          </label>
          <label className="field">
            <span>ФИО пациента</span>
            <input value={patientName} onChange={(event) => setPatientName(event.target.value)} required />
          </label>
          <label className="field">
            <span>Возраст</span>
            <input
              type="number"
              min="0"
              max="130"
              value={age}
              onChange={(event) => setAge(event.target.value)}
            />
          </label>
        </div>
        <div className="intake-grid intake-inputs">
          <label className="field">
            <span>Файлы обследования</span>
            <input ref={fileRef} type="file" accept=".pdf,.docx,.txt" multiple />
          </label>
          <label className="field">
            <span>Или вставьте текст результата</span>
            <textarea
              rows={4}
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder="Заключение, жалобы, показатели…"
            />
          </label>
        </div>
        <div className="actions">
          <button className="btn primary" type="submit" disabled={busy}>
            {busy ? 'Обработка…' : 'Обработать и отправить на проверку'}
          </button>
          {status && <span className="hint">{status}</span>}
          {error && <span className="error">{error}</span>}
        </div>
      </form>
    </section>
  )
}