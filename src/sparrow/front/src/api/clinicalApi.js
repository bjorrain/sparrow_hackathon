const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  })

  if (!res.ok) {
    let message = `${res.status} ${res.statusText}`
    try {
      const body = await res.json()
      message = body.detail || body.message || message
    } catch {
      try {
        const text = await res.text()
        if (text) message = text
      } catch {
        // ignore non-JSON errors
      }
    }
    throw new Error(message)
  }

  if (res.status === 204) return null
  return res.json()
}

export async function extractClinicalFindings(text) {
  if (!text || !text.trim()) {
    throw new Error('Введите текст описания для анализа.')
  }

  return request('/extract', {
    method: 'POST',
    body: JSON.stringify({ text }),
  })
}
