import React, { useEffect, useState } from 'react'
import { post } from '@app/api.js'
import Icon from '@app/icons.jsx'
import CompareButton from './CompareButton.jsx'
import './compare.css'

// «Было / стало»: обычная выдача сайта (рейтинг, «до моря по прямой») рядом с нашей —
// и где обычная разочаровала бы гостя. Ответ на вопрос эксперта «повлияет ли это на выбор»
const rub = n => `${n.toLocaleString('ru-RU')} ₽`
const dist = m => (m < 1000 ? `${m} м` : `${(m / 1000).toFixed(1).replace('.', ',')} км`)
const plural = (n, one, few, many) => {
  const m10 = n % 10, m100 = n % 100
  return m10 === 1 && m100 !== 11 ? one : m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20) ? few : many
}

export function useBaseline(on, month) {
  const [data, setData] = useState(null)
  useEffect(() => {
    if (!on.length) { setData(null); return }
    let alive = true
    post('/api/compare/baseline', { lenses: on, month }).then(d => alive && setData(d)).catch(() => alive && setData(null))
    return () => { alive = false }
  }, [on.join(','), month])
  return data
}

export function ModeSwitch({ mode, setMode }) {
  return (
    <div className="bs-seg" role="tablist">
      <button className={mode === 'base' ? 'on' : ''} onClick={() => setMode('base')}>Обычный поиск</button>
      <button className={mode === 'okno' ? 'on ok' : ''} onClick={() => setMode('okno')}>С О!кном</button>
    </div>
  )
}

// плашка над нашей выдачей: кто поднялся, хотя на сайте был бы глубоко внизу
export function RiseNote({ data, list }) {
  if (!data) return null
  const up = list.slice(0, 5).find(x => x.info?.fit === 'all' && !((data.rank[x.h.id] || 1e9) <= 10))
  if (!up) return null
  const r = data.rank[up.h.id]
  return (
    <div className="bs-banner good"><Icon name="sparkle" size={22} />
      <div><b>«{up.h.name.replace(/^[«"]|[»"]$/g, '')}»</b> {r ? `в обычном поиске — на ${r}-м месте` : 'в обычный поиск не попадает'}, а здесь подходит по всем вашим условиям.</div>
    </div>
  )
}

export function BaselineList({ data, byId, onSelect }) {
  if (!data) return <div className="count">Собираем обычную выдачу…</div>
  const s = data.summary
  return (
    <>
      {s.traps > 0
        ? <div className="bs-banner warn"><Icon name="alert" size={22} />
            <div><b>{s.traps} {plural(s.traps, 'отель', 'отеля', 'отелей')} из первой десятки {plural(s.traps, 'разочаровал', 'разочаровали', 'разочаровали')} бы вас</b>
              {s.kinds.length ? `: ${s.kinds.join(', ')}` : ''}.
              {s.unknown > 0 && ` Ещё про ${s.unknown} мы знаем не всё.`} В «С О!кном» их нет наверху.</div></div>
        : <div className="bs-banner"><Icon name="check" size={22} /><div>В первой десятке обычного поиска подвохов по вашим условиям не нашли.</div></div>}
      <div className="count">Как отсортировал бы обычный сайт: рейтинг, потом «до моря по прямой»</div>
      {data.hotels.map(b => {
        const h = byId[b.id]
        if (!h) return null
        return (
          <div key={b.id} className={`row result bs-row ${b.traps.length ? 'trap' : ''}`} onClick={() => onSelect(b.id)}>
            <div className="bs-rank">{b.rank}</div>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div className="nm">{h.name}{b.our_rank > 10 && <span className="bs-move down">у нас {b.our_rank}-й</span>}</div>
              <div className="sub">
                <span>{h.kind_ru}</span>
                {b.line_m != null && <span>{dist(b.line_m)} до моря по прямой</span>}
              </div>
              <div className="why">
                {b.traps.map(t => <div key={t} className="no bs-trap"><Icon name="alert" size={16} />{t}</div>)}
                {b.ok.map(o => <div key={o.text} className={o.state}><Icon name={o.state === 'match' ? 'check' : 'half'} size={16} />{o.text}</div>)}
                {b.unknown.map(t => <div key={t} className="unknown"><Icon name="question" size={16} />{t}</div>)}
              </div>
            </div>
            <div className="pr"><b>{rub(h.price_rub)}</b><small>за ночь</small><CompareButton id={b.id} /></div>
          </div>
        )
      })}
    </>
  )
}
