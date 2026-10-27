import React, { useEffect, useState } from 'react'
import { api, post } from '@app/api.js'
import Icon from '@app/icons.jsx'
import { NIGHTS, tripDates } from './common.jsx'
import './trip.css'

// Бронь с пожеланием в карточке отеля: пожелание собирается само из выбранного в «О!кне» и фактов,
// гость может убрать пункт. Бронь — демо: сохраняем выбор и открываем «Мою поездку» (#trip/<id брони>).
export default function BookBox({ hotelId, view, month, price }) {
  const [w, setW] = useState(null)
  const [drop, setDrop] = useState([])
  const [last, setLast] = useState(null)
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    setLast(null)
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
        floor: w?.floor || view?.floor || null, drop })
      location.hash = `trip/${b.id}`
    } catch { setBusy(false) }
  }
  const items = w?.items || []
  const kept = items.filter(x => !drop.includes(x.id))

  return (
    <div className="block">
      <h2>Бронирование</h2>
      <div className="tr-total"><b>{(price * NIGHTS).toLocaleString('ru-RU')} ₽</b>за {NIGHTS} ночей, {tripDates(month)}
        <span className="chip" style={{ padding: '2px 9px', fontSize: 12, color: 'var(--muted)' }}>демо-цена</span></div>
      {items.length > 0 && <>
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
        })}</ul>
      </>}
      <button className="tr-btn pri" disabled={busy} onClick={book}>
        {kept.length ? 'Забронировать с пожеланием' : 'Забронировать'}</button>
      {last && <a className="tr-link" href={`#trip/${last.id}`}><Icon name="calendar" size={18} />Ваша поездка: {last.status_text.toLowerCase()}</a>}
    </div>
  )
}
