import React, { useEffect, useState } from 'react'
import { api } from '@app/api.js'
import Icon from '@app/icons.jsx'
import { HOW, sureWord } from '@features/facts/frontend/FactList.jsx'
import { SiteQuote } from '@features/web_sources/frontend/SiteQuote.jsx'
import { outingColor } from './DayRoute.jsx'
import './day.css'

const SURE = { hi: 'Данные надёжные.', mid: 'Это расчёт: на месте может немного отличаться.', lo: 'Это примерная оценка.' }

// Откуда мы это знаем: с сайта отеля — дословная цитата, иначе — как посчитали и насколько уверены
function How({ facts }) {
  const f0 = facts[0]
  if (f0.source?.startsWith('web:')) return <div className="how">Это слова отеля, мы их не проверяли. На сайте:
    <SiteQuote quote={f0.evidence?.quote} url={f0.evidence?.url} date={f0.evidence?.fetched_at} /></div>
  const c = Math.min(...facts.map(f => f.confidence))
  return <div className="how">{HOW[f0.source] || 'Посчитали по открытым данным.'} {SURE[sureWord(c)[1]]}</div>
}

// Кружок справа у места вне отеля: идём (номер места за день) или не пойдём
function StopToggle({ on, n, outing, onToggle }) {
  return (
    <button className={`day-stop ${on ? 'on' : ''}`} style={on && outing ? { background: outingColor(outing), borderColor: outingColor(outing) } : null} onClick={e => { e.stopPropagation(); onToggle() }}
      aria-label={on ? 'Не пойду сюда' : 'Пойду сюда'} title={on ? 'Не пойду сюда' : 'Пойду сюда'}>
      {on ? (n || <Icon name="check" size={14} />) : '+'}
    </button>
  )
}

// Одна сцена дня: время, что происходит, по клику — откуда мы это знаем.
// Строка пути (kind=walk) — тоньше: когда вышли и сколько идти; у места, куда пришли, — «до скольких» там
function Scene({ s, stop }) {
  const [open, setOpen] = useState(false)
  const toggle = () => setOpen(!open)
  const walk = s.kind === 'walk'
  return (
    <li className={`day-scene ${walk ? 'day-walk' : ''} ${s.good ? '' : 'warn'} ${stop && !stop.on ? 'off' : ''}`} onClick={toggle}
      tabIndex={0} aria-expanded={open} onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), toggle())}>
      <time>{s.time}{s.visit && <small>до {s.visit.until}</small>}</time>
      {walk ? <span className="day-dot" style={{ background: outingColor(s.outing) }} /> : <span className="day-dot"><Icon name={s.icon} size={18} /></span>}
      <div className="day-body">
        <b>{s.title}</b>
        {s.note && <span>{s.note}</span>}
        {open && s.facts.length > 0 && <How facts={s.facts} />}
      </div>
      {stop && <StopToggle {...stop} />}
    </li>
  )
}

const plural = (n, one, few, many) => {
  const m10 = n % 10, m100 = n % 100
  return m10 === 1 && m100 !== 11 ? one : m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20) ? few : many
}

// Ночная аптека — «на всякий случай», в план дня по умолчанию не ставим
const SKIP0 = ['night']

// «Ваш день здесь»: лента одного дня из фактов, для стороны и этажа, выбранных в «О!кне».
// Места вне отеля — выходы из отеля: в ленте время в пути и на месте, на карте — линия на каждый выход.
// Куда не пойдёт, гость убирает кружком справа. onRoute(маршрут|null) рисует выходы на карте,
// routeShown — они сейчас на карте (а не путь до пляжа и т.п.)
export default function DayPanel({ hotelId, month, view, onRoute, routeShown }) {
  const [kids, setKids] = useState(false)
  const [d, setD] = useState(null)
  const [skip, setSkip] = useState(SKIP0)

  useEffect(() => { setD(null); setSkip(SKIP0) }, [hotelId])  // не показываем день прошлого отеля, пока грузится новый

  const q = () => {
    const p = new URLSearchParams({ month })
    if (view?.facade) p.set('facade', view.facade)
    if (view?.floor) p.set('floor', view.floor)
    if (kids) p.set('mode', 'kids')
    if (skip.length) p.set('skip', skip.join(','))
    return p
  }
  const deps = [hotelId, month, view?.facade, view?.floor, kids, skip.join(',')]
  useEffect(() => {
    let alive = true
    api(`/api/hotels/${hotelId}/day?${q()}`).then(x => alive && setD(x)).catch(() => alive && setD(false))
    return () => { alive = false }
  }, deps)

  const showRoute = () => api(`/api/hotels/${hotelId}/day/route?${q()}`)
    .then(x => onRoute?.(x)).catch(() => onRoute?.({ title: 'Маршрут дня', none: true }))
  // выходы уже на карте — пересобираем, когда гость убрал место, сменил сторону или режим
  useEffect(() => { if (routeShown) showRoute() }, deps)

  const toggleStop = id => setSkip(skip.includes(id) ? skip.filter(x => x !== id) : [...skip, id])

  if (d === false || (d && d.scenes.length < 2)) return null
  if (!d) return <div className="block muted">Собираем ваш день…</div>
  const stops = d.scenes.filter(s => s.stop)
  const w = d.walk
  return (
    <div className="block day">
      <div className="day-head">
        <h2>Ваш день здесь</h2>
        <div className="pills"><button className={kids ? 'on' : ''} onClick={() => setKids(!kids)}>
          <Icon name="child" size={16} />С ребёнком</button></div>
      </div>
      {stops.length > 0 && (
        <div className={`day-route ${routeShown ? 'on' : ''}`}>
          <Icon name="pin" size={18} />
          <span>{w.outings
            ? <>{w.outings} {plural(w.outings, 'выход', 'выхода', 'выходов')} из отеля, пешком всего <b>{w.minutes} мин</b>{w.up_m >= 10 ? <>, в гору <b>{w.up_m} м</b></> : ''}</>
            : 'Весь день у отеля. Отметьте кружком, куда пойдёте'}</span>
          {w.outings > 0 && (routeShown
            ? <button onClick={() => onRoute?.(null)}>Скрыть с карты</button>
            : <button onClick={showRoute}>На карте</button>)}
        </div>)}
      <ol className="day-line">{d.scenes.map(s => <Scene key={(s.kind || '') + s.time + s.title} s={s}
        stop={s.stop && { on: !skip.includes(s.stop.id), n: s.visit?.n, outing: s.visit?.outing, onToggle: () => toggleStop(s.stop.id) }} />)}</ol>
    </div>
  )
}
