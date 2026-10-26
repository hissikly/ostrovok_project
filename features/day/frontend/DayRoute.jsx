import React from 'react'
import './day.css'

// цвет каждого выхода из отеля — линия, номера мест и метка в плашке; первый — оранжевый, как любой путь от отеля
export const OUTING_COLORS = ['#FF6B1A', '#8B5CF6', '#0E9F8E', '#E11D48']
export const outingColor = n => OUTING_COLORS[(n - 1) % OUTING_COLORS.length]

const km = m => m < 1000 ? `${m} м` : `${(m / 1000).toFixed(1).replace('.', ',')} км`

// Плашка на карте для выходов из отеля: каждый выход отдельно (когда, сколько идти, куда), внизу — итог
export default function DayRouteInfo({ r }) {
  if (!r.outings?.length) return <div className="route-info"><b>{r.title}</b><span>Весь день у отеля</span></div>
  return (
    <div className="route-info">
      <b>Выходы из отеля</b>
      {r.outings.map(o => (
        <div key={o.n} className="day-outing">
          <span><i className="day-outing-line" style={{ background: outingColor(o.n) }} />{o.name} в {o.depart}</span><b>{o.minutes} мин</b>
          <div className="day-route-stops">{r.stops.filter(s => s.outing === o.n).map(s => <span key={s.id}><i style={{ background: outingColor(o.n) }}>{s.n}</i>{s.name}</span>)}</div>
        </div>
      ))}
      <div className="route-notes">Всего пешком {r.minutes} мин, {km(r.meters)}{r.up_m >= 10 ? `, в гору ${r.up_m} м` : ''}</div>
    </div>
  )
}
