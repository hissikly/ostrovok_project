import React, { useEffect, useState } from 'react'
import { api } from '@app/api.js'
import Icon from '@app/icons.jsx'
import './characteristics.css'

// Блок карточки «Что ещё узнали»: ответы агента-исследователя по характеристикам, которые считает он сам
// (Wi-Fi и всё, что добавили описанием), и по клику — как он искал: какие источники пробовал и что каждый сказал.
const STEP = { found: ['check', 'ok'], absent: ['x', 'no'], nothing: ['question', 'none'], unavailable: ['clock', 'none'],
  asked: ['mail', 'asked'] }

function Item({ it, onPlace, activePlace }) {
  const [open, setOpen] = useState(false)
  const near = it.fact?.characteristic.startsWith('near:') && it.fact.value.meters != null
  const text = it.text || (it.state === 'asked' ? 'Пока не знаем — спросили у отеля' : 'Пока не знаем')
  const decisive = it.trace.find(t => ['found', 'absent'].includes(t.status)) || it.trace.find(t => t.status === 'asked')
  return (
    <div className="fact" onClick={() => setOpen(!open)}>
      <div className="ic"><Icon name={it.icon || 'pin'} /></div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="t">{it.title}</div>
        <div className={`s ${it.fact ? '' : 'muted'}`}>{text}</div>
        {!open && decisive && <div className="ch-src">{decisive.status === 'asked' ? 'Открытые данные молчат' : `Источник: ${decisive.title.toLowerCase()}`}</div>}
        {near && onPlace && <div className={`more-link ${activePlace === it.id ? 'on' : ''}`}
          onClick={e => { e.stopPropagation(); onPlace(activePlace === it.id ? null : it.id) }}>Показать на карте</div>}
        {open && <ol className="ch-trace">{it.trace.map((t, i) => {
          const [ic, cls] = STEP[t.status] || STEP.nothing
          return <li key={i} className={cls}><Icon name={ic} size={16} /><span><b>{t.title}</b>{t.note}</span></li>
        })}</ol>}
      </div>
    </div>
  )
}

export default function AgentFacts({ hotelId, onPlace, activePlace }) {
  const [items, setItems] = useState([])
  useEffect(() => {
    setItems([])
    api(`/api/hotels/${hotelId}/agent`).then(setItems).catch(() => setItems([]))
  }, [hotelId])
  if (!items.length) return null
  const sorted = [...items].sort((a, b) => !!b.fact - !!a.fact)
  return (
    <div className="block">
      <h2>Что ещё узнали</h2>
      <p className="lead">Агент сам выбирал, где искать ответ: карта, отметки отеля, его ответы, сайт. Нажмите — покажем путь поиска.</p>
      {sorted.map(it => <Item key={it.id} it={it} onPlace={onPlace} activePlace={activePlace} />)}
    </div>
  )
}
