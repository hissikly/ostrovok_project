import React, { useEffect, useState } from 'react'
import { api } from '@app/api.js'
import Icon from '@app/icons.jsx'
import { HOW, sureWord, FoldButton } from '@features/facts/frontend/FactList.jsx'
import { SiteQuote } from '@features/web_sources/frontend/SiteQuote.jsx'
import { outingColor } from './DayRoute.jsx'
import { useInterests } from '@features/trip_plan/frontend/interests.js'
import TripFooter, { PinButton } from '@features/trip_plan/frontend/TripDay.jsx'
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
function Scene({ s, stop, pin }) {
  const [open, setOpen] = useState(false)
  const toggle = () => setOpen(!open)
  const walk = s.kind === 'walk'
  return (
    <li className={`day-scene ${walk ? 'day-walk' : ''} ${s.good ? '' : 'warn'} ${stop && !stop.on ? 'off' : ''} ${s.interest === 'surprise' ? 'surprise' : ''}`} onClick={toggle}
      tabIndex={0} aria-expanded={open} onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), toggle())}>
      <time>{s.time}</time>
      {walk ? <span className="day-dot" style={{ background: outingColor(s.outing) }} /> : <span className="day-dot"><Icon name={s.icon} size={18} /></span>}
      <div className="day-body">
        {s.interest_title && !walk && <span className="trip-for">{s.interest_title}</span>}
        <b>{s.title}{s.visit && !walk && <em className="day-until">до {s.visit.until}</em>}</b>
        {s.note && <span>{s.note}</span>}
        {open && s.facts.length > 0 && <How facts={s.facts} />}
      </div>
      {pin ? <div className="trip-side">{stop && <StopToggle {...stop} />}<PinButton {...pin} /></div> : stop && <StopToggle {...stop} />}
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
  // день по интересам (features/trip_plan): номер варианта и закреплённые гостем места {интерес: место}
  const [interests] = useInterests()
  const [variant, setVariant] = useState(0)
  const [pins, setPins] = useState({})
  const trip = interests.length > 0   // интересы выбраны — день всегда по ним («с детьми» — один из интересов)
  const [d, setD] = useState(null)
  const [skip, setSkip] = useState(SKIP0)
  const [folded, setFolded] = useState(() => { try { return localStorage.getItem('fold:day') === '1' } catch { return false } })
  const fold = () => { try { localStorage.setItem('fold:day', folded ? '0' : '1') } catch { /* не помним */ } setFolded(!folded) }

  useEffect(() => { setD(null); setSkip(SKIP0); setVariant(0); setPins({}) }, [hotelId])  // не показываем день прошлого отеля, пока грузится новый
  useEffect(() => { setVariant(0); setPins({}) }, [interests.join(',')])

  const q = () => {
    const p = new URLSearchParams({ month })
    if (view?.facade) p.set('facade', view.facade)
    if (view?.floor) p.set('floor', view.floor)
    if (skip.length) p.set('skip', skip.join(','))
    if (trip) {
      p.set('interests', interests.join(','))
      if (variant) p.set('variant', variant)
      const pp = Object.entries(pins).map(([k, v]) => `${k}:${v}`)
      if (pp.length) p.set('pins', pp.join(','))
    }
    return p
  }
  const deps = [hotelId, month, view?.facade, view?.floor, skip.join(','), trip, interests.join(','), variant, JSON.stringify(pins)]
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
  const togglePin = s => setPins(p => { const n = { ...p }; if (n[s.interest]) delete n[s.interest]; else n[s.interest] = s.place; return n })

  if (d === false || (d && d.scenes.length < 2)) return null
  if (!d) return <div className="block muted">Собираем ваш день…</div>
  const stops = d.scenes.filter(s => s.stop)
  const w = d.walk
  return (
    <div className="block day">
      <div className="day-head">
        <h2>Ваш день здесь</h2>
        <div className="pills"><FoldButton folded={folded} onClick={fold} /></div>
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
      {!folded && <ol key={trip ? `v${variant}` : 'day'} className={`day-line ${trip ? 'trip-fade' : ''}`}>{d.scenes.map(s => <Scene key={(s.kind || '') + s.time + s.title} s={s}
        stop={s.stop && { on: !skip.includes(s.stop.id), n: s.visit?.n, outing: s.visit?.outing, onToggle: () => toggleStop(s.stop.id) }}
        pin={s.alts > 1 && s.kind !== 'walk' && { on: pins[s.interest] === s.place, onClick: () => togglePin(s) }} />)}</ol>}
      {!folded && d.plan && <TripFooter plan={d.plan} onAgain={() => setVariant(variant + 1)} />}
    </div>
  )
}
