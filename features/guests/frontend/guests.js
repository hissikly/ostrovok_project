import { useEffect, useState } from 'react'
import { useInterests } from '@features/trip_plan/frontend/interests.js'

// Кто едет: {adults, children: [возраст, …]}. Живёт в браузере (без регистрации), общий для шапки,
// «Моей поездки» и брони: изменили в одном месте — событие trip:guests, остальные подхватывают.
// Дети в поездке — значит и интерес «С детьми» (features/trip_plan): день и чемодан собираются с ребёнком
const KEY = 'trip:guests'
export const GUESTS0 = { adults: 2, children: [] }
export const MAX_ADULTS = 6
export const MAX_CHILDREN = 4
const read = () => {
  try {
    const g = JSON.parse(localStorage.getItem(KEY))
    return g && g.adults >= 1 && Array.isArray(g.children) ? g : GUESTS0
  } catch { return GUESTS0 }
}

export function useGuests() {
  const [g, setG] = useState(read)
  const [interests, setInterests] = useInterests()
  useEffect(() => {
    const on = () => setG(read())
    addEventListener('trip:guests', on)
    return () => removeEventListener('trip:guests', on)
  }, [])
  const set = next => {
    try { localStorage.setItem(KEY, JSON.stringify(next)) } catch { /* не помним между визитами */ }
    setG(next)
    dispatchEvent(new Event('trip:guests'))
    const had = g.children.length > 0, has = next.children.length > 0
    if (has && !had && !interests.includes('kids')) setInterests([...interests, 'kids'])
    if (!has && had) setInterests(interests.filter(x => x !== 'kids'))
  }
  return [g, set]
}

const plural = (n, one, few, many) => {
  const m10 = n % 10, m100 = n % 100
  return m10 === 1 && m100 !== 11 ? one : m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20) ? few : many
}
export const ageWord = a => a === 0 ? 'до года' : `${a} ${plural(a, 'год', 'года', 'лет')}`
export const adultsWord = n => `${n} ${plural(n, 'взрослый', 'взрослых', 'взрослых')}`
export const childrenWord = n => `${n} ${plural(n, 'ребёнок', 'ребёнка', 'детей')}`
// «2 взрослых», «2 взрослых, 1 ребёнок»; full — с возрастом детей, для отеля: «2 взрослых, ребёнок 5 лет»
export function guestsText(g, full = false) {
  if (!g) return adultsWord(2)
  const kids = g.children || []
  if (!kids.length) return adultsWord(g.adults)
  if (!full) return `${adultsWord(g.adults)}, ${childrenWord(kids.length)}`
  return `${adultsWord(g.adults)}, ${kids.length === 1 ? 'ребёнок' : 'дети'} ${kids.map(ageWord).join(', ')}`
}
