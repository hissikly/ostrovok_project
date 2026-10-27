import React, { useEffect, useState } from 'react'
import { api, post } from '@app/api.js'
import Icon from '@app/icons.jsx'
import { NIGHTS, tripDates } from './common.jsx'
import { guestsText } from '@features/guests/frontend/guests.js'
import './trip.css'

// Экстранет: брони с пожеланием. Отель отвечает «Подтверждаем» или «Не сможем, предложим…» — гость видит ответ в «Моей поездке»
function Booking({ b, hotelId, onDone }) {
  const [decline, setDecline] = useState(null)
  const answer = async (a, text = '') => { onDone(await post(`/api/hotelier/${hotelId}/bookings/${b.id}`, { answer: a, text })); setDecline(null) }
  return (
    <div className="ext-q">
      <div className="tr-ext-meta">{tripDates(b.month)}, {NIGHTS} ночей, {guestsText(b.guests, true)}</div>
      <div className="tr-ext-wish">{b.wish.text || 'Без особых пожеланий'}</div>
      {b.wish.items.length > 0 && <ul className="tr-ext-why">{b.wish.items.map(it => <li key={it.id}><b>{it.text}.</b> {it.own ? 'Гость написал сам' : it.reason}</li>)}</ul>}
      {b.status !== 'sent'
        ? <div className="ext-ok" style={b.status === 'declined' ? { color: '#8A4A00' } : null}>
            <Icon name={b.status === 'confirmed' ? 'check' : 'mail'} size={18} />
            {b.status === 'confirmed' ? 'Подтвердили' : 'Предложили другое'}{b.hotel_reply ? `: «${b.hotel_reply}»` : ''}</div>
        : decline !== null
          ? <>
              <textarea value={decline} onChange={e => setDecline(e.target.value)} placeholder="Что можете предложить? Например: запад, но 5 этаж" />
              <div className="ext-actions">
                <button className="ext-btn pri" disabled={!decline.trim()} onClick={() => answer('decline', decline)}>Отправить гостю</button>
                <button className="ext-btn sec" onClick={() => setDecline(null)}>Отмена</button>
              </div>
            </>
          : <div className="ext-actions">
              <button className="ext-btn pri" onClick={() => answer('confirm')}>Подтверждаем</button>
              <button className="ext-btn sec" onClick={() => setDecline('')}>Не сможем, предложим…</button>
            </div>}
    </div>
  )
}

export default function HotelBookings({ hotelId }) {
  const [list, setList] = useState(null)
  useEffect(() => { setList(null); api(`/api/hotelier/${hotelId}/bookings`).then(setList).catch(() => setList([])) }, [hotelId])
  if (!list?.length) return null
  const update = b => setList(list.map(x => x.id === b.id ? b : x))
  const waiting = list.filter(b => b.status === 'sent').length
  return (
    <section className="block">
      <h2>Брони с пожеланием</h2>
      <p className="lead">{waiting ? 'Гости выбирали номер по виду и тишине. Ответьте, сможете ли выполнить пожелание.' : 'На все пожелания вы ответили.'}</p>
      {list.map(b => <Booking key={b.id} b={b} hotelId={hotelId} onDone={update} />)}
    </section>
  )
}
