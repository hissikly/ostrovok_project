import React, { useEffect, useRef, useState } from 'react'
import Icon from '@app/icons.jsx'
import { useCatalog, useInterests } from './interests.js'
import './trip.css'

// Кнопка в плашке поездки рядом с датами и гостями: «Чем заняться» → окно с плитками интересов
export default function InterestsButton() {
  const [list, setList] = useInterests()
  const catalog = useCatalog()
  const [open, setOpen] = useState(false)
  const box = useRef(null)
  useEffect(() => {
    if (!open) return
    const off = e => { if (box.current && !box.current.contains(e.target)) setOpen(false) }
    const esc = e => e.key === 'Escape' && setOpen(false)
    addEventListener('mousedown', off)
    addEventListener('keydown', esc)
    return () => { removeEventListener('mousedown', off); removeEventListener('keydown', esc) }
  }, [open])
  const names = catalog.filter(i => list.includes(i.id)).map(i => i.title.toLowerCase())
  const label = names.length ? names.join(', ').replace(/^./, c => c.toUpperCase()) : 'Чем заняться'
  const toggle = id => setList(list.includes(id) ? list.filter(x => x !== id) : [...list, id])

  return (
    <span className="trip-want" ref={box}>
      <button className={`trip-want-btn ${list.length ? 'on' : ''}`} onClick={() => setOpen(!open)} aria-expanded={open} title={label}>
        <Icon name="sparkle" size={17} /><span className="lbl">{label}</span>
      </button>
      {open && (
        <div className="trip-pop" role="dialog" aria-label="Чем хотите заняться">
          <h3>Чем хотите заняться?</h3>
          <p>Соберём день у каждого отеля из ваших интересов</p>
          <div className="trip-ints">
            {catalog.map(i => (
              <button key={i.id} className={list.includes(i.id) ? 'on' : ''} onClick={() => toggle(i.id)} aria-pressed={list.includes(i.id)}>
                <Icon name={i.icon} size={20} />{i.title}
              </button>
            ))}
          </div>
          <button className="trip-done" onClick={() => setOpen(false)}>Готово</button>
          <div className="trip-note"><Icon name="check" size={14} />Хранится только в этом браузере</div>
        </div>
      )}
    </span>
  )
}

// Строка в списке отелей: «Всё пешком» или «2 из 3 пешком» и что далеко
export function FitLine({ fit }) {
  if (!fit || !fit.all) return null
  const full = fit.good === fit.all
  const far = fit.far[0]
  return (
    <div className="trip-fit">
      <span className={full ? 'all' : ''}>{full ? 'Ваш день — всё пешком' : `${fit.good} из ${fit.all} пешком`}</span>
      {!full && far?.title && <small>{far.title}</small>}
    </div>
  )
}
