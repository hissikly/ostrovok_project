import { useEffect, useState } from 'react'
import { api, post } from '@app/api.js'

// Интересы гостя живут в браузере (без регистрации) и общие для шапки, списка и «Ваш день здесь»:
// изменили в шапке — событие trip:interests, остальные подхватывают
const KEY = 'trip:interests'
const read = () => { try { return JSON.parse(localStorage.getItem(KEY)) || [] } catch { return [] } }

export function useInterests() {
  const [list, setList] = useState(read)
  useEffect(() => {
    const on = () => setList(read())
    addEventListener('trip:interests', on)
    return () => removeEventListener('trip:interests', on)
  }, [])
  const set = next => {
    try { localStorage.setItem(KEY, JSON.stringify(next)) } catch { /* не помним между визитами */ }
    setList(next)
    dispatchEvent(new Event('trip:interests'))
  }
  return [list, set]
}

let catalog = null
export function useCatalog() {
  const [c, setC] = useState(catalog)
  useEffect(() => { if (!catalog) api('/api/trip/interests').then(x => { catalog = x; setC(x) }).catch(() => setC([])) }, [])
  return c || []
}

// Сколько интересов у каждого отеля закрываются пешком: {hotel_id: {good, all, far, unknown, score}}
const fits = {}
export function useFit(interests) {
  const k = interests.join(',')
  const [f, setF] = useState(() => fits[k] || null)
  useEffect(() => {
    if (!k) { setF(null); return }
    if (fits[k]) { setF(fits[k]); return }
    let alive = true
    post('/api/trip/fit', { interests }).then(x => { fits[k] = x; alive && setF(x) }).catch(() => alive && setF(null))
    return () => { alive = false }
  }, [k])
  return f
}
