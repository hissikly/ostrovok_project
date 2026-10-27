import React, { useEffect, useRef, useState } from 'react'
import Icon from '@app/icons.jsx'
import { useCatalog, useInterests } from './interests.js'
import './trip.css'

// Подсказку у кнопки показываем один раз — пока гость не выбрал интересы и не закрыл её
const HINT = 'trip:hint'
// ?hint в адресе — показать снова (для показа и записи видео)
const hintSeen = () => { if (location.search.includes('hint')) return false; try { return localStorage.getItem(HINT) === '1' } catch { return true } }

// Кнопка в плашке поездки рядом с датами и гостями: «Чем заняться» → окно с плитками интересов
export default function InterestsButton() {
  const [list, setList] = useInterests()
  // «С детьми» не выбирают здесь: он сам включается, когда в «Кто едет» есть дети (features/guests)
  const catalog = useCatalog().filter(i => i.id !== 'kids')
  const [open, setOpen] = useState(false)
  const [hint, setHint] = useState(false)
  useEffect(() => {
    if ((list.length && !location.search.includes('hint')) || hintSeen()) return
    const t = setTimeout(() => setHint(true), 900)   // после загрузки карты, чтобы не мигало
    return () => clearTimeout(t)
  }, [])
  const closeHint = () => { try { localStorage.setItem(HINT, '1') } catch { /* покажем ещё раз */ } setHint(false) }
  const openPop = () => { closeHint(); setOpen(!open) }
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
      <button className={`trip-want-btn ${list.length ? 'on' : ''} ${hint ? 'hinted' : ''}`} onClick={openPop} aria-expanded={open} title={label}>
        <Icon name="sparkle" size={17} /><span className="lbl">{label}</span>
      </button>
      {hint && !open && (
        <div className="trip-hint" role="status">
          <b>Чем хотите заняться в Сочи?</b>
          <span>Отметьте интересы — соберём ваш день у каждого отеля и покажем, где всё рядом</span>
          <div><button className="go" onClick={openPop}>Выбрать</button><button onClick={closeHint}>Не сейчас</button></div>
        </div>
      )}
      {open && (
        <div className="trip-pop" role="dialog" aria-label="Чем хотите заняться">
          <h3>Чем хотите заняться?</h3>
          <div className="trip-ints">
            {catalog.map(i => (
              <button key={i.id} className={list.includes(i.id) ? 'on' : ''} onClick={() => toggle(i.id)} aria-pressed={list.includes(i.id)}>
                <Icon name={i.icon} size={20} />{i.title}
              </button>
            ))}
          </div>
          <button className="trip-done" onClick={() => setOpen(false)}>Готово</button>
        </div>
      )}
    </span>
  )
}

// Строка в списке отелей — текстом с иконкой интересов, без плашки: салатовая плашка в строке уже у «О!кна»
export function FitLine({ fit }) {
  if (!fit || !fit.all) return null
  const full = fit.good === fit.all
  const far = fit.far[0]
  return (
    <div className={`trip-fit ${full ? 'all' : ''}`}>
      <Icon name="sparkle" size={15} />
      <span>{full ? 'Ваш день — всё пешком' : `Ваш день: ${fit.good} из ${fit.all} пешком`}</span>
      {!full && far?.title && <small>{far.title}</small>}
    </div>
  )
}
