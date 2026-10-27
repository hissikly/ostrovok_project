import React, { useEffect, useRef, useState } from 'react'
import Icon from '@app/icons.jsx'
import { useGuests, guestsText, ageWord, MAX_ADULTS, MAX_CHILDREN } from './guests.js'
import './guests.css'

const AGES = Array.from({ length: 18 }, (_, i) => i)

function Stepper({ title, note, value, min, max, onChange }) {
  return (
    <div className="gs-row">
      <div><b>{title}</b>{note && <span>{note}</span>}</div>
      <div className="gs-step">
        <button onClick={() => onChange(value - 1)} disabled={value <= min} aria-label={`Меньше: ${title}`}>−</button>
        <output aria-live="polite">{value}</output>
        <button onClick={() => onChange(value + 1)} disabled={value >= max} aria-label={`Больше: ${title}`}>+</button>
      </div>
    </div>
  )
}

// Кнопка «Гости» в плашке поездки: взрослые, дети и возраст каждого ребёнка
export default function GuestsButton() {
  const [g, setG] = useGuests()
  const [open, setOpen] = useState(false)
  // место окна запоминаем при открытии: подписи в плашке меняют ширину (дети, интересы), а окно стоит на месте
  const [at, setAt] = useState(null)
  const box = useRef(null)
  const toggle = () => {
    const r = box.current.getBoundingClientRect()
    setAt(innerWidth > 640 ? { position: 'fixed', left: Math.max(16, r.left), top: r.bottom + 10, right: 'auto' } : null)
    setOpen(!open)
  }
  useEffect(() => {
    if (!open) return
    const off = e => { if (box.current && !box.current.contains(e.target)) setOpen(false) }
    const esc = e => e.key === 'Escape' && setOpen(false)
    addEventListener('mousedown', off)
    addEventListener('keydown', esc)
    return () => { removeEventListener('mousedown', off); removeEventListener('keydown', esc) }
  }, [open])
  const setKids = n => setG({ ...g, children: n > g.children.length ? [...g.children, 5] : g.children.slice(0, n) })
  const setAge = (i, a) => setG({ ...g, children: g.children.map((x, j) => j === i ? a : x) })

  return (
    <span className="gs" ref={box}>
      <button className="gs-btn" onClick={toggle} aria-expanded={open} aria-label={`Гости: ${guestsText(g)}`}>
        <Icon name="user" size={17} /><span className="lbl">{guestsText(g)}</span>
      </button>
      {open && (
        <div className="gs-pop" style={at || undefined} role="dialog" aria-label="Гости">
          <h3>Кто едет?</h3>
          <Stepper title="Взрослые" value={g.adults} min={1} max={MAX_ADULTS} onChange={n => setG({ ...g, adults: n })} />
          <Stepper title="Дети" note="До 17 лет" value={g.children.length} min={0} max={MAX_CHILDREN} onChange={setKids} />
          {g.children.map((a, i) => (
            <label key={i} className="gs-age">
              <span>Возраст {g.children.length > 1 ? `${i + 1}-го ребёнка` : 'ребёнка'}</span>
              <select value={a} onChange={e => setAge(i, +e.target.value)}>
                {AGES.map(x => <option key={x} value={x}>{ageWord(x)}</option>)}
              </select>
            </label>
          ))}
          {g.children.length > 0 && <p className="gs-note"><Icon name="child" size={16} />Соберём день и чемодан с ребёнком, а отелю передадим возраст</p>}
          <button className="gs-done" onClick={() => setOpen(false)}>Готово</button>
        </div>
      )}
    </span>
  )
}
