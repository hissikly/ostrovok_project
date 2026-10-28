// Сервер не ответил (сеть) или ответил 5xx — это временная ошибка: App покажет плашку «Временная ошибка»,
// остальные блоки продолжают работать. 4xx — обычный ответ «такого нет», о нём не шумим.
export const TEMP_ERROR = 'Временная ошибка: часть данных не загрузилась. Попробуйте через минуту'

async function call(path, init) {
  let r
  try {
    r = await fetch(path, init)
  } catch (e) {
    dispatchEvent(new CustomEvent('api-down', { detail: { path } }))
    throw new Error(TEMP_ERROR)
  }
  if (!r.ok) {
    if (r.status >= 500) {
      dispatchEvent(new CustomEvent('api-down', { detail: { path, status: r.status } }))
      throw new Error(TEMP_ERROR)
    }
    throw new Error(`${path}: HTTP ${r.status}`)
  }
  return r.json()
}

export const api = path => call(path)

export const post = (path, body) =>
  call(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
