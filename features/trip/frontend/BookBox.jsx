import React, { useEffect, useRef, useState } from 'react'
import { api, post } from '@app/api.js'
import Icon from '@app/icons.jsx'
import { NIGHTS, tripDates } from './common.jsx'
import { useGuests, guestsText } from '@features/guests/frontend/guests.js'
import './trip.css'

// Бронь с пожеланием в карточке отеля: пожелание собирается само из выбранного в «О!кне» и фактов,
// гость может убрать пункт и дописать своё (до трёх, его словами). Бронь — демо: сохраняем выбор и открываем «Мою поездку» (#trip/<id брони>).
const MAX_OWN = 3
const HINTS = ['Подальше от лифта', 'Раздельные кровати', 'Ранний заезд']

// «+ Своё пожелание»: свёрнуто в ссылку, по нажатию — строка ввода и пара подсказок
function OwnWish({ count, onAdd }) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState('')
  const input = useRef(null)
  useEffect(() => { if (open) input.current?.focus() }, [open])
  if (count >= MAX_OWN) return null
  const add = t => {
    const v = t.trim().replace(/[.\s]+$/, '')
    if (!v) return
    onAdd(v); setText(''); setOpen(false)
  }
  if (!open) return (
    <button className="tr-add" onClick={() => setOpen(true)}><span aria-hidden="true">+</span>Своё пожелание</button>
  )
  return (
    <div className="tr-own">
      <form className="tr-own-row" onSubmit={e => { e.preventDefault(); add(text) }}>
        <input ref={input} value={text} maxLength={120} placeholder="Например, номер подальше от лифта"
          aria-label="Своё пожелание отелю" onChange={e => setText(e.target.value)}
          onKeyDown={e => e.key === 'Escape' && (setText(''), setOpen(false))} />
        <button type="submit" disabled={!text.trim()}>Добавить</button>
      </form>
      {!text && <div className="tr-own-hints">{HINTS.map(h =>
        <button key={h} type="button" onClick={() => add(h)}>{h}</button>)}</div>}
    </div>
  )
}

export default function BookBox({ hotelId, view, month, price }) {
  const [w, setW] = useState(null)
  const [drop, setDrop] = useState([])
  const [own, setOwn] = useState([])
  const [guests] = useGuests()
  const [last, setLast] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setLast(null); setOwn([])
    api(`/api/bookings?hotel_id=${hotelId}`).then(bs => { setLast(bs[0] || null) }).catch(() => {})
  }, [hotelId])
  useEffect(() => {
    setDrop([])
    const p = new URLSearchParams({ month })
    if (view?.facade) p.set('facade', view.facade)
    if (view?.floor) p.set('floor', view.floor)
    let alive = true
    api(`/api/hotels/${hotelId}/request?${p}`).then(x => alive && setW(x)).catch(() => alive && setW(null))
    return () => { alive = false }
  }, [hotelId, month, view?.facade, view?.floor])

  const toggle = id => setDrop(drop.includes(id) ? drop.filter(x => x !== id) : [...drop, id])
  const book = async () => {
    setBusy(true)
    try {
      const b = await post('/api/bookings', { hotel_id: hotelId, month, facade: w?.facade || view?.facade || null,
        floor: w?.floor || view?.floor || null, drop, guests, own })
      location.hash = `trip/${b.id}`
    } catch { setBusy(false) }
  }
  const items = w?.items || []
  const kept = items.filter(x => !drop.includes(x.id))

  return (
    <div className="block">
      <h2>Бронирование</h2>
      <div className="tr-total"><b>{(price * NIGHTS).toLocaleString('ru-RU')} ₽</b>за {NIGHTS} ночей, {tripDates(month)}, {guestsText(guests)}
        <span className="chip" style={{ padding: '2px 9px', fontSize: 12, color: 'var(--muted)' }}>демо-цена</span></div>
      {(items.length > 0 || own.length > 0) && <>
        <div className="tr-cap">Попросим отель</div>
        <ul className="tr-wish">{items.map(it => {
          const off = drop.includes(it.id)
          return (
            <li key={it.id} className={off ? 'off' : ''}>
              <Icon name="check" size={20} />
              <div><b>{it.text}</b><span>{it.reason}</span></div>
              <button className="tr-x" onClick={() => toggle(it.id)} aria-label={off ? `Вернуть: ${it.text}` : `Убрать: ${it.text}`}
                title={off ? 'Вернуть' : 'Убрать'}><Icon name={off ? 'check' : 'x'} size={16} /></button>
            </li>
          )
        })}
        {own.map((t, i) => (
          <li key={`own${i}`} className="own">
            <Icon name="check" size={20} />
            <div><b>{t}</b><span>Своими словами</span></div>
            <button className="tr-x" onClick={() => setOwn(own.filter((_, j) => j !== i))} aria-label={`Убрать: ${t}`} title="Убрать">
              <Icon name="x" size={16} /></button>
          </li>
        ))}</ul>
      </>}
      <OwnWish count={own.length} onAdd={t => setOwn([...own, t])} />
      <button className="tr-btn pri" disabled={busy} onClick={book}>
        {kept.length || own.length ? 'Забронировать с пожеланием' : 'Забронировать'}</button>
      {last && <a className="tr-link" href={`#trip/${last.id}`}><Icon name="calendar" size={18} />Ваша поездка: {last.status_text.toLowerCase()}</a>}
    </div>
  )
}
