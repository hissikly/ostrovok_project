import React, { useEffect, useMemo, useState } from 'react'
import { api } from '@app/api.js'
import Icon from '@app/icons.jsx'
import './sights.css'

// Пока данные собраны только по Сочи — остальные города честно «скоро»
const CITIES = [
  { name: 'Сочи', on: true },
  { name: 'Анапа' }, { name: 'Калининград' }, { name: 'Казань' }, { name: 'Санкт-Петербург' },
]

function Credit({ c }) {
  if (!c) return null
  return <a className="sg-credit" href={c.page} target="_blank" rel="noreferrer" onClick={e => e.stopPropagation()}
    title={`${c.author} · ${c.license}`}>Фото: {c.author.length > 28 ? `${c.author.slice(0, 26)}…` : c.author} · {c.license}</a>
}

function Card({ s, chosen, onLive }) {
  return (
    <div className={`sg-card ${chosen ? 'on' : ''}`}>
      <div className="sg-img"><img src={s.photo} alt={s.name} loading="lazy" /><Credit c={s.credit} /></div>
      <div className="sg-body">
        <div className="sg-tags">{s.tags.map(t => <span key={t}>{t}</span>)}</div>
        <h3>{s.name}</h3>
        <p>{s.about}</p>
        <div className="sg-foot">
          <span className="sg-dur"><Icon name="clock" size={15} />{s.duration}</span>
          <button className="sg-live" onClick={() => onLive(s)}>{chosen ? 'Уже в подборе' : 'Жить рядом'} →</button>
        </div>
        {!s.walkable && <div className="sg-far">Пешком от отелей не дойти — подберём тех, откуда ближе ехать</div>}
      </div>
    </div>
  )
}

export default function City({ on, onLive, onExit }) {
  const [list, setList] = useState(null)
  const [tag, setTag] = useState(null)
  const [soon, setSoon] = useState(null)
  useEffect(() => { api('/api/sights').then(setList).catch(() => setList([])) }, [])
  const tags = useMemo(() => [...new Set((list || []).flatMap(s => s.tags))], [list])
  const shown = (list || []).filter(s => !tag || s.tags.includes(tag))
  return (
    <div className="sg">
      <div className="sg-top">
        <button className="back" onClick={onExit}>← К отелям</button>
        <div className="sg-cities">
          {CITIES.map(c => (
            <button key={c.name} className={c.on ? 'on' : 'soon'} onClick={() => setSoon(c.on ? null : c.name)}>
              <Icon name="pin" size={16} />{c.name}{!c.on && <small>скоро</small>}
            </button>
          ))}
        </div>
        {soon && <div className="sg-soon">{soon} — скоро. Пока факты об отелях собраны только по Большому Сочи</div>}
      </div>
      <h1>Что посмотреть в Сочи</h1>
      {tags.length > 0 && (
        <div className="lenses sg-filter">
          <button className={!tag ? 'on' : ''} onClick={() => setTag(null)}>Все</button>
          {tags.map(t => <button key={t} className={tag === t ? 'on' : ''} onClick={() => setTag(tag === t ? null : t)}>{t}</button>)}
        </div>
      )}
      {!list ? <div className="muted">Загружаем…</div> : (
        <div className="sg-grid">
          {shown.map(s => <Card key={s.id} s={s} chosen={on.includes(s.lens)} onLive={onLive} />)}
        </div>
      )}
    </div>
  )
}
