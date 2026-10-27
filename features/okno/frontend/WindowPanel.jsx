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
// share — доля моря в виде с этого этажа, для подписи в легенде: длинные синие лучи на карте выглядят «большими»,
// даже когда моря краешек
function coneGeo(w) {
  return {
    type: 'FeatureCollection', share: w.sea_share,
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

// Картинка к плашке заката: небо, солнце у горизонта и что под ним — море, дальние дома, соседний дом или склон;
// aside — солнце за краем рамы окна
function SunsetArt({ kind }) {
  const sky = kind === 'none' ? ['#E3EBFD', '#F6F8FC'] : ['#FFC98A', '#FFF1DF']
  return (
    <svg className="sunset-art" viewBox="0 0 64 64" aria-hidden="true">
      <defs><linearGradient id={`sk-${kind}`} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor={sky[0]} /><stop offset="1" stopColor={sky[1]} /></linearGradient></defs>
      <rect width="64" height="64" rx="16" fill={`url(#sk-${kind})`} />
      {kind !== 'none' && kind !== 'aside' && <g>
        <circle cx="32" cy="42" r="12" fill="#FF8A1F" />
        {[-60, -30, 0, 30, 60].map(a => {
          const r = a * Math.PI / 180
          return <line key={a} x1={32 + Math.sin(r) * 16} y1={42 - Math.cos(r) * 16} x2={32 + Math.sin(r) * 21} y2={42 - Math.cos(r) * 21}
            stroke="#FF8A1F" strokeWidth="2.5" strokeLinecap="round" />
        })}
      </g>}
      {kind === 'sea' && <g>
        <path d="M0 42h64v6a16 16 0 0 1 -16 16H16A16 16 0 0 1 0 48z" fill="#4C7DFF" />
        <path d="M14 50h12M34 50h16M22 56h20" stroke="#fff" strokeWidth="2" strokeLinecap="round" opacity=".8" />
      </g>}
      {kind === 'horizon' && <path d="M0 42h8v-5h6v5h4v-8h7v8h14v-4h6v4h5v-6h6v6h8v6a16 16 0 0 1 -16 16H16A16 16 0 0 1 0 48z" fill="#8A93A6" />}
      {kind === 'building' && <g><path d="M0 50h64v-2a16 16 0 0 1 -16 16H16A16 16 0 0 1 0 48z" fill="#C9CDD4" />
        <rect x="18" y="20" width="30" height="44" fill="#8A93A6" />
        {[26, 34, 42, 50].map(y => <path key={y} d={`M23 ${y}h6M37 ${y}h6`} stroke="#C9CDD4" strokeWidth="3" />)}</g>}
      {kind === 'terrain' && <path d="M0 64V38q14 -16 30 -6t34 -4v20a16 16 0 0 1 -16 16z" fill="#7FA36B" />}
      {kind === 'aside' && <g>
        <rect x="22" y="10" width="36" height="44" rx="3" fill="#fff" fillOpacity=".5" stroke="#8A93A6" strokeWidth="4" />
        <path d="M40 10v44M22 32h36" stroke="#8A93A6" strokeWidth="3" />
        <circle cx="13" cy="44" r="9" fill="#FF8A1F" />
      </g>}
      {kind === 'none' && <g><rect x="16" y="14" width="32" height="50" fill="#C9CDD4" />
        {[22, 31, 40, 49].map(y => <path key={y} d={`M21 ${y}h8M35 ${y}h8`} stroke="#EEF0F3" strokeWidth="3.5" />)}
        <circle cx="52" cy="12" r="6" fill="#FFC98A" /></g>}
    </svg>
  )
}

// Закат в даты поездки. Салатовая плашка — только для хорошей новости.
function Sunset({ sun }) {
  const trip = sun.find(s => s.month === TRIP_MONTH)
  let title, text, good = false, kind = 'none'
  if (trip?.sets_into_sea) {
    title = 'Закат над морем прямо из окна'
    text = `В ${MONTH_IN[TRIP_MONTH]} солнце садится в море в ${trip.sunset_astro}`
    good = true; kind = 'sea'
  } else if (trip?.hidden_by === 'aside') {
    // солнце садится далеко сбоку от оси окна — увидите, только если подойти к стеклу
    title = 'Закат сбоку от окна'
    text = `Солнце сядет ${trip.side === 'left' ? 'слева' : 'справа'}, у края окна`
    kind = 'aside'
  } else if (trip?.sun_hidden_at && trip.minutes_earlier <= 3) {
    // скрывается за дальними домами у самого горизонта — для человека это обычный закат
    title = 'Закат виден из окна'
    text = `В ${MONTH_IN[TRIP_MONTH]} солнце сядет в ${trip.sunset_astro} за дальними домами у горизонта`
    good = true; kind = 'horizon'
  } else if (trip?.sun_hidden_at && ['building', 'terrain'].includes(trip.hidden_by)) {
    title = trip.hidden_by === 'building' ? 'Закат закроет соседний дом' : 'Солнце уйдёт за склон'
    text = `В ${MONTH_IN[TRIP_MONTH]} оно скроется в ${trip.sun_hidden_at}, за ${trip.minutes_earlier} мин до заката`
    kind = trip.hidden_by
  } else {
    title = 'Заката из этих окон не видно'
    text = ''
  }
  return <div className={`sunset ${good ? '' : 'off'}`}><SunsetArt kind={kind} /><div><b>{title}</b>{text}</div></div>
}

// Много этажей: полоска столбиков — высота = сколько моря видно с этажа; сразу видно, «с какого этажа море»
function FloorStrip({ floors, shares, value, onPick }) {
  return (
    <div className="floor-strip">
      <div className="bars">{floors.map(f => (
        <button key={f} className={f === value ? 'on' : ''} title={`${f} этаж`} aria-label={`${f} этаж`} onClick={() => onPick(f)}>
          <i style={{ height: `${Math.max(8, Math.round(shares[f] * 100))}%` }} />
        </button>
      ))}</div>
      <div className="ticks"><span>1</span><b>{value} этаж</b><span>{floors[floors.length - 1]}</span></div>
    </div>
  )
}

export default function WindowPanel({ hotelId, onCone, onPick }) {
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
  // выбранные сторона и этаж — для «Ваш день здесь»
  useEffect(() => { if (w) onPick?.({ facade: w.facade, floor: w.floor }) }, [w?.facade, w?.floor])

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
        {floors.length <= 8
          ? <div className="pills">{floors.map(f =>
            <button key={f} className={f === w.floor ? 'on' : ''} onClick={() => setFloor(f)}>{f}</button>)}</div>
          : <FloorStrip floors={floors} shares={meta.facades[side].floors} value={w.floor} onPick={setFloor} />}
      </div>
      <div className="verdict">{verdict(w.sea_share)}</div>
      <div className="meter"><i style={{ width: `${Math.round(w.sea_share * 100)}%` }} /></div>
      <Sunset sun={w.sun} />
    </div>
  )
}
