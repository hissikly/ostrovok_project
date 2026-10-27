import React, { useEffect, useState } from 'react'
import { api } from '@app/api.js'
import Icon from '@app/icons.jsx'
import { plural } from '@features/trip/frontend/common.jsx'
import './profile.css'

const SHOW = 2   // в карточке сначала два отзыва, остальные — по «Ещё»

function Stars({ n }) {
  return <span className="pf-stars small" aria-label={`${n} из 5`}>{[1, 2, 3, 4, 5].map(i =>
    <span key={i} className={i <= n ? 'on' : ''}><Icon name="star" size={15} /></span>)}</span>
}

function Item({ r }) {
  return (
    <div className="rv-item">
      <div className="rv-top">
        <Stars n={r.stars} />
        <span className="rv-who">{r.guest} · {r.when}</span>
        {r.demo && <span className="rv-demo">демо</span>}
      </div>
      {r.text && <p>{r.text}</p>}
      {(r.yes.length > 0 || r.no.length > 0) && (
        <div className="rv-checks">
          {r.yes.map(t => <span key={t} className="rv-yes"><Icon name="check" size={14} />{t}</span>)}
          {r.no.map(t => <span key={t} className="rv-no"><Icon name="x" size={14} />{t}</span>)}
        </div>
      )}
    </div>
  )
}

// Отзывы гостей после поездки (features/profile): звёзды, текст и что из обещанного совпало.
// extranet — вид для отеля: средняя оценка, что чаще всего не совпало, все отзывы сразу
export default function GuestReviews({ hotelId, extranet = false }) {
  const [d, setD] = useState(null)
  const [all, setAll] = useState(false)
  useEffect(() => { setD(null); setAll(false); api(`/api/hotels/${hotelId}/reviews`).then(setD).catch(() => setD(null)) }, [hotelId])
  if (!d || (!d.count && !extranet)) return null
  const shown = extranet || all ? d.items : d.items.slice(0, SHOW)
  const Tag = extranet ? 'section' : 'div'
  return (
    <Tag className="block rv">
      <div className="rv-head">
        <h2>Отзывы после поездки</h2>
        {d.count > 0 && <span className="rv-avg"><Icon name="star" size={16} />{String(d.avg).replace('.', ',')}
          <small>{d.count} {plural(d.count, 'отзыв', 'отзыва', 'отзывов')}</small></span>}
      </div>
      <p className="lead">{extranet
        ? 'Гости оценили поездку и отметили, что совпало с описанием. Где не совпало — стоит поправить описание или номер.'
        : 'Гости, которые бронировали через О!кно, отметили, что совпало с обещанным.'}</p>
      {extranet && d.mismatches.length > 0 && (
        <div className="rv-miss"><Icon name="alert" size={18} /><div><b>Чаще всего не совпадало</b>
          {d.mismatches.map(m => <span key={m.title}>{m.title} — {m.count} {plural(m.count, 'гость', 'гостя', 'гостей')}</span>)}</div></div>
      )}
      {!d.count && <div className="muted">Отзывов после поездки пока нет</div>}
      {shown.map(r => <Item key={r.id} r={r} />)}
      {!extranet && d.count > SHOW && <button className="pf-link" onClick={() => setAll(!all)}>
        {all ? 'Свернуть' : `Ещё ${d.count - SHOW} ${plural(d.count - SHOW, 'отзыв', 'отзыва', 'отзывов')}`}</button>}
      {d.demo > 0 && <div className="rv-note">{d.demo === d.count ? 'Все отзывы демо' : `Из них демо: ${d.demo}`}</div>}
    </Tag>
  )
}
