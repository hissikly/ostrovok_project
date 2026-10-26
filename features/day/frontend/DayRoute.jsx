import React from 'react'
import './day.css'

const km = m => m < 1000 ? `${m} м` : `${(m / 1000).toFixed(1).replace('.', ',')} км`

// Плашка на карте для маршрута дня: сколько идти за весь день и сколько в гору
export default function DayRouteInfo({ r }) {
  if (!r.stops.length) return <div className="route-info"><b>{r.title}</b><span>Все места убраны — гуляем у отеля</span></div>
  return (
    <div className="route-info">
      <b>{r.title}</b>
      <div className="route-row"><span>Пешком</span><b>{r.minutes} мин</b><i>{km(r.meters)} за день</i></div>
      <div className="route-row"><span>В гору</span><b>{r.up_m} м</b><i>{r.up_m >= 30 ? `будто на ${Math.round(r.up_m / 3)}-й этаж` : 'почти ровно'}</i></div>
      <div className="day-route-stops">{r.stops.map(s => <span key={s.id}><i>{s.n}</i>{s.name}</span>)}</div>
    </div>
  )
}
