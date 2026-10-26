import React, { useEffect, useMemo, useState } from 'react'
import { api, post } from './api.js'
import Icon from './icons.jsx'
import HotelMap from '@features/hotels/frontend/HotelMap.jsx'
import SearchPanel from '@features/search/frontend/SearchPanel.jsx'
import HotelCard from '@features/hotels/frontend/HotelCard.jsx'
import Extranet from '@features/hotelier/frontend/Extranet.jsx'
import AddCharacteristic from '@features/characteristics/frontend/AddCharacteristic.jsx'
import InterestsButton from '@features/trip_plan/frontend/Interests.jsx'

const MONTH = ['', 'январь', 'февраль', 'март', 'апрель', 'май', 'июнь', 'июль', 'август', 'сентябрь', 'октябрь', 'ноябрь', 'декабрь']

export default function App() {
  const [hotels, setHotels] = useState([])
  // выбранный отель живёт в адресе (#w201474333) — ссылкой на отель можно поделиться
  const [selected, setSelectedState] = useState(() => location.hash.slice(1) || null)
  const setSelected = id => { history.replaceState(null, '', id ? `#${id}` : location.pathname); setSelectedState(id) }
  useEffect(() => {
    const onHash = () => setSelectedState(location.hash.slice(1) || null)
    addEventListener('hashchange', onHash)
    return () => removeEventListener('hashchange', onHash)
  }, [])
  const [cone, setCone] = useState(null)   // лучи «вид из окна» для карты
  const [error, setError] = useState(null)
  // подбор: включённые линзы, месяц поездки, ответ /api/search
  const [lenses, setLenses] = useState([])
  const [on, setOn] = useState([])
  const [month, setMonth] = useState(5)
  const [result, setResult] = useState(null)

  useEffect(() => { api('/api/hotels').then(setHotels).catch(e => setError(String(e))) }, [])
  useEffect(() => { api('/api/lenses').then(setLenses).catch(e => setError(String(e))) }, [])
  useEffect(() => {
    if (!on.length) { setResult(null); return }
    let alive = true
    post('/api/search', { lenses: on, month }).then(r => alive && setResult(r)).catch(e => setError(String(e)))
    return () => { alive = false }
  }, [on, month])
  // иконка и группа каждого типа «что рядом» — из каталога фильтров (линзы near_<id>)
  const nearMeta = useMemo(() => Object.fromEntries(lenses.filter(l => l.id.startsWith('near_'))
    .map(l => [l.id.slice(5), { icon: l.icon, group: l.group }])), [lenses])
  const fits = useMemo(() => result && Object.fromEntries(result.hotels.map(r => [r.id, r.fit])), [result])
  // у открытого отеля показываем на карте найденное рядом: магазин, парк, аптеку…
  const pois = useMemo(() => {
    const r = result && selected && result.hotels.find(x => x.id === selected)
    const pts = (r?.reasons || []).filter(x => x.point)
    return pts.length ? { type: 'FeatureCollection', features: pts.map(x => ({ type: 'Feature',
      properties: { name: x.point.name }, geometry: { type: 'Point', coordinates: [x.point.lon, x.point.lat] } })) } : null
  }, [result, selected])
  // места одного типа рядом с открытым отелем (клик по «Что рядом пешком»)
  const [places, setPlaces] = useState(null)
  // пеший маршрут на карте: до пляжа или до выбранного места
  const [route, setRoute] = useState(null)
  useEffect(() => { if (!selected) setCone(null); setPlaces(null); setRoute(null) }, [selected])
  const showRoute = (url, title) => api(url).then(r => setRoute({ ...r, title })).catch(() => setRoute({ title, none: true }))
  const routeTo = p => showRoute(`/api/hotels/${selected}/route?lat=${p.lat}&lon=${p.lon}`,
    p.name ? `До ${/[«"„“]/.test(p.name) ? p.name : `«${p.name}»`}` : `До места: ${p.kind.toLowerCase()}`)
  const showPlaces = spec => {
    if (!spec) { setPlaces(null); setRoute(null); return }
    api(`/api/hotels/${selected}/nearby/${spec}`).then(d => {
      setPlaces(d)
      if (d.items.length) routeTo(d.items[0]); else setRoute(null)
    })
  }
  const showBeach = () => { setPlaces(null); showRoute(`/api/hotels/${selected}/beach-route`, 'До пляжа') }
  const closeMapBox = () => { setPlaces(null); setRoute(null) }

  const sel = useMemo(() => hotels.find(h => h.id === selected), [hotels, selected])

  // «Научить О!кно»: новая характеристика описанием (#admin)
  if (selected === 'admin') return <AddCharacteristic onExit={() => setSelected(null)} />
  // Экстранет отельера: #extranet/<id отеля>
  if (selected?.startsWith('extranet')) {
    const hid = selected.split('/')[1] || 'w201474333'
    return <Extranet hotelId={hid} hotels={hotels} onHotel={id => setSelected(`extranet/${id}`)}
      onExit={() => setSelected(hid)} />
  }

  return (
    <div className="layout">
      <header className="hdr">
        <div className="logo">Островок!</div>
        <span className="chip lime">О!кно</span>
        <div className="trip">
          <span><Icon name="pin" size={17} />Сочи</span>
          <span><Icon name="calendar" size={17} />{month === 5 ? '12–19 мая' : MONTH[month]}</span>
          <span><Icon name="user" size={17} />2 взрослых</span>
          <InterestsButton />
        </div>
        <button className="for-hotels" onClick={() => setSelected(`extranet/${sel?.id || 'w201474333'}`)}>Для отелей</button>
      </header>
      <div className="main">
        <aside className="panel">
          {error && <div className="chip warn">{error}</div>}
          {sel
            ? <HotelCard id={sel.id} month={month} onBack={() => setSelected(null)} onCone={setCone} onPlace={showPlaces} onBeach={showBeach} onDayRoute={r => { setPlaces(null); setRoute(r) }}
              places={places} routeTitle={route?.title} nearMeta={nearMeta} />
            : <SearchPanel hotels={hotels} lenses={lenses} on={on} setOn={setOn} setMonth={setMonth}
                result={result} onSelect={setSelected} />}
        </aside>
        <section className="map">
          <HotelMap hotels={hotels} selected={selected} onSelect={setSelected} cone={route || places ? null : cone} fits={fits} pois={pois} places={places} route={route}
            onPlaceClick={routeTo} onCloseBox={closeMapBox} />
        </section>
      </div>
    </div>
  )
}
