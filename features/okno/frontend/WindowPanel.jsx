import React, { useEffect, useState } from 'react'
import { api } from '@app/api.js'

const SIDE = { N: 'север', E: 'восток', S: 'юг', W: 'запад' }
const MONTH_IN = ['', 'январе', 'феврале', 'марте', 'апреле', 'мае', 'июне', 'июле', 'августе', 'сентябре', 'октябре', 'ноябре', 'декабре']
const TRIP_MONTH = 5        // даты поездки из шапки (12–19 мая) — пока зашиты
const R = 6371000

function dest([lat, lon], az, d) {
  const a = az * Math.PI / 180
  return [lon + d * Math.sin(a) / (R * Math.cos(lat * Math.PI / 180)) * 180 / Math.PI,
          lat + d * Math.cos(a) / R * 180 / Math.PI]
}

// Лучи обзора для карты: куда видно море — длинные синие, куда упирается дом — короткие красные.
// Лучи в сушу и склоны не рисуем: без легенды они только путают.
function coneGeo(w) {
  return {
    type: 'FeatureCollection',
    features: [
      ...w.profile.filter(([, kind, , sea]) => sea || kind === 'b').map(([az, kind, dist, sea]) => {
        const k = sea ? 's' : kind
        const L = sea ? 2500 : Math.max(dist, 8)
        return { type: 'Feature', properties: { k },
          geometry: { type: 'LineString', coordinates: [[w.eye[1], w.eye[0]], dest(w.eye, az, L)] } }
      }),
      // само окно — откуда идут лучи
      { type: 'Feature', properties: { k: 'eye' }, geometry: { type: 'Point', coordinates: [w.eye[1], w.eye[0]] } },
    ],
  }
}

function verdict(share) {
  if (share >= 0.75) return 'Море почти во весь вид'
  if (share >= 0.45) return 'Море в половине вида'
  if (share >= 0.15) return 'Море видно частично'
  if (share > 0) return 'Море видно краешком'
  return 'Моря из этого окна не видно'
}

// Закат в даты поездки. Салатовая плашка — только для хорошей новости.
function Sunset({ sun }) {
  const trip = sun.find(s => s.month === TRIP_MONTH)
  let title, text, good = false
  if (trip?.sets_into_sea) {
    title = 'Закат над морем прямо из окна'
    text = `В ${MONTH_IN[TRIP_MONTH]} солнце садится в море в ${trip.sunset_astro}`
    good = true
  } else if (trip?.sun_hidden_at && trip.minutes_earlier <= 3) {
    // скрывается за дальними домами у самого горизонта — для человека это обычный закат
    title = 'Закат виден из окна'
    text = `В ${MONTH_IN[TRIP_MONTH]} солнце сядет в ${trip.sunset_astro} за дальними домами у горизонта`
    good = true
  } else if (trip?.sun_hidden_at && ['building', 'terrain'].includes(trip.hidden_by)) {
    title = trip.hidden_by === 'building' ? 'Закат закроет соседний дом' : 'Солнце уйдёт за склон'
    text = `В ${MONTH_IN[TRIP_MONTH]} оно скроется в ${trip.sun_hidden_at}, за ${trip.minutes_earlier} мин до заката`
  } else {
    title = 'Заката из этих окон не видно'
    text = 'Солнце садится с другой стороны здания'
  }
  return <div className={`sunset ${good ? '' : 'off'}`}><b>{title}</b>{text}</div>
}

export default function WindowPanel({ hotelId, onCone }) {
  const [meta, setMeta] = useState(null)
  const [side, setSide] = useState(null)
  const [floor, setFloor] = useState(null)
  const [w, setW] = useState(null)

  useEffect(() => {
    setMeta(null); setW(null)
    api(`/api/hotels/${hotelId}/window`).then(m => {
      if (!m.computed) { setMeta(false); return }
      setMeta(m)
      const s = m.facades.W ? 'W' : Object.keys(m.facades)[0]
      setSide(s)
      setFloor(Math.max(...Object.keys(m.facades[s].floors).map(Number)))
    }).catch(() => setMeta(false))
  }, [hotelId])

  useEffect(() => {
    if (!side || !floor) return
    api(`/api/hotels/${hotelId}/window?facade=${side}&floor=${floor}`).then(x => { setW(x); onCone(coneGeo(x)) })
  }, [hotelId, side, floor])

  useEffect(() => () => onCone(null), [])

  if (meta === false) return null
  if (!meta || !w) return <div className="block muted">Смотрим, что видно из окон…</div>
  const sides = Object.keys(meta.facades).sort((a, b) =>
    Math.max(...Object.values(meta.facades[b].floors)) - Math.max(...Object.values(meta.facades[a].floors)))
  const floors = Object.keys(meta.facades[side].floors).map(Number).sort((a, b) => a - b)

  return (
    <div className="block">
      <h2>О!кно</h2>
      <p className="lead">Выберите, куда выходят окна и этаж — покажем, что вы увидите.</p>
      <div className="pick"><span>Окна на</span>
        <div className="pills">{sides.map(s =>
          <button key={s} className={s === side ? 'on' : ''} onClick={() => setSide(s)}>{SIDE[s]}</button>)}</div>
      </div>
      <div className="pick"><span>Этаж</span>
        <div className="pills">{floors.map(f =>
          <button key={f} className={f === w.floor ? 'on' : ''} onClick={() => setFloor(f)}>{f}</button>)}</div>
      </div>
      <div className="verdict">{verdict(w.sea_share)}</div>
      <div className="meter"><i style={{ width: `${Math.round(w.sea_share * 100)}%` }} /></div>
      <Sunset sun={w.sun} />
    </div>
  )
}
