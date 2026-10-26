import React, { useEffect, useState } from 'react'
import { api } from '@app/api.js'
import Icon from '@app/icons.jsx'
import { HOW, sureWord } from '@features/facts/frontend/FactList.jsx'
import './day.css'

const MONTH_IN = ['', 'январе', 'феврале', 'марте', 'апреле', 'мае', 'июне', 'июле', 'августе', 'сентябре', 'октябре', 'ноябре', 'декабре']
const SIDE_TO = { N: 'на север', E: 'на восток', S: 'на юг', W: 'на запад' }
const SURE = { hi: 'Данные надёжные.', mid: 'Это расчёт: на месте может немного отличаться.', lo: 'Это примерная оценка.' }

// Одна сцена дня: время, что происходит, по клику — откуда мы это знаем
function Scene({ s }) {
  const [open, setOpen] = useState(false)
  const f0 = s.facts[0]
  const c = Math.min(...s.facts.map(f => f.confidence))
  return (
    <li className={`day-scene ${s.good ? '' : 'warn'}`} onClick={() => setOpen(!open)}>
      <time>{s.time}</time>
      <span className="day-dot"><Icon name={s.icon} size={18} /></span>
      <div className="day-body">
        <b>{s.title}</b>
        {s.note && <span>{s.note}</span>}
        {open && f0 && <div className="how">{HOW[f0.source] || 'Посчитали по открытым данным.'} {SURE[sureWord(c)[1]]}</div>}
      </div>
    </li>
  )
}

// «Ваш день здесь»: лента одного дня из фактов, для стороны и этажа, выбранных в «О!кне»
export default function DayPanel({ hotelId, month, view }) {
  const [kids, setKids] = useState(false)
  const [d, setD] = useState(null)

  useEffect(() => {
    const q = new URLSearchParams({ month })
    if (view?.facade) q.set('facade', view.facade)
    if (view?.floor) q.set('floor', view.floor)
    if (kids) q.set('mode', 'kids')
    let alive = true
    api(`/api/hotels/${hotelId}/day?${q}`).then(x => alive && setD(x)).catch(() => alive && setD(false))
    return () => { alive = false }
  }, [hotelId, month, view?.facade, view?.floor, kids])

  if (d === false || (d && d.scenes.length < 2)) return null
  if (!d) return <div className="block muted">Собираем ваш день…</div>
  return (
    <div className="block day">
      <div className="day-head">
        <h2>Ваш день здесь</h2>
        <div className="pills"><button className={kids ? 'on' : ''} onClick={() => setKids(!kids)}>
          <Icon name="child" size={16} />С ребёнком</button></div>
      </div>
      <p className="lead">Один день в {MONTH_IN[d.month]}{d.facade ? `, окна ${SIDE_TO[d.facade]}, ${d.floor} этаж` : ''}. Только из проверенных фактов.</p>
      <ol className="day-line">{d.scenes.map(s => <Scene key={s.time + s.title} s={s} />)}</ol>
    </div>
  )
}
