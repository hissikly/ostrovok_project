import React, { useState } from 'react'
import Icon from '@app/icons.jsx'
import './trip.css'

const plural = (n, one, few, many) => {
  const m10 = n % 10, m100 = n % 100
  return m10 === 1 && m100 !== 11 ? one : m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20) ? few : many
}

// Булавка у места по интересу: оставить его в любом варианте дня
export function PinButton({ on, onClick }) {
  return (
    <button className={`trip-pin ${on ? 'on' : ''}`} onClick={e => { e.stopPropagation(); onClick() }}
      aria-pressed={on} title={on ? 'Открепить' : 'Оставить в любом варианте'} aria-label={on ? 'Открепить' : 'Оставить в любом варианте'}>
      <svg width="16" height="16" viewBox="0 0 24 24" fill={on ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.8"
        strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M9 4h6l-1 6 3 3H7l3-3zM12 13v7" /></svg>
    </button>
  )
}

const MARK = { ok: 'check', swap: 'half', none: 'question', pin: 'pin', surprise: 'sparkle', look: 'eye' }

// Под лентой: «Другой вариант дня» и свёрнутая трасса агента «Как собрали этот день»
export default function TripFooter({ plan, pinned, onAgain }) {
  const [open, setOpen] = useState(false)
  const more = plan.variants - 1
  return (
    <div className="trip-foot">
      <button className="trip-again" onClick={onAgain} disabled={more < 1}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"
          strokeLinejoin="round" aria-hidden="true"><path d="M20 11a8 8 0 0 0-14.9-3.5M4 4v4h4M4 13a8 8 0 0 0 14.9 3.5M20 20v-4h-4" /></svg>
        Другой вариант дня
      </button>
      <div className="trip-again-note">
        {more > 0 ? `Ещё ${more} ${plural(more, 'вариант', 'варианта', 'вариантов')} из проверенных мест${plan.variant % 2 === 0 ? ', иногда с сюрпризом' : ''}`
          : pinned ? 'Остальное — единственные подходящие места рядом' : 'Других подходящих мест рядом нет'}
      </div>
      <button className={`trip-how ${open ? 'open' : ''}`} onClick={() => setOpen(!open)} aria-expanded={open}>
        <Icon name="eye" size={17} />Как собрали этот день
        <svg className="chev" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
          strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6" /></svg>
      </button>
      {open && (
        <ul className="trip-trace">
          {plan.trace.map((x, i) => (
            <li key={i} className={x.kind}><Icon name={MARK[x.kind] || 'check'} size={15} />
              <div>{x.text}{x.source && <small>{x.source}</small>}</div></li>
          ))}
        </ul>
      )}
    </div>
  )
}
