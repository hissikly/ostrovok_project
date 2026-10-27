import { useEffect, useState } from 'react'

// Отели «в сравнении» живут в браузере и общие для выдачи, карточки и корзинки внизу:
// изменили в одном месте — событие compare:ids, остальные подхватывают
const KEY = 'compare:ids'
export const MAX = 4
const read = () => { try { return JSON.parse(localStorage.getItem(KEY)) || [] } catch { return [] } }

export function useCompare() {
  const [ids, setIds] = useState(read)
  useEffect(() => {
    const on = () => setIds(read())
    addEventListener('compare:ids', on)
    return () => removeEventListener('compare:ids', on)
  }, [])
  const set = next => {
    try { localStorage.setItem(KEY, JSON.stringify(next)) } catch { /* не помним между визитами */ }
    setIds(next)
    dispatchEvent(new Event('compare:ids'))
  }
  const toggle = id => set(ids.includes(id) ? ids.filter(x => x !== id) : ids.length < MAX ? [...ids, id] : ids)
  return { ids, set, toggle, remove: id => set(ids.filter(x => x !== id)), clear: () => set([]) }
}
