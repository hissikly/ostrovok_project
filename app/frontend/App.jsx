import React, { useEffect, useMemo, useState } from 'react'
import { api, post, TEMP_ERROR } from './api.js'
import ErrorBoundary from './ErrorBoundary.jsx'
import Icon from './icons.jsx'
import HotelMap from '@features/hotels/frontend/HotelMap.jsx'
import SearchPanel from '@features/search/frontend/SearchPanel.jsx'
import HotelCard from '@features/hotels/frontend/HotelCard.jsx'
import Extranet from '@features/hotelier/frontend/Extranet.jsx'
import AddCharacteristic from '@features/characteristics/frontend/AddCharacteristic.jsx'
import Trip from '@features/trip/frontend/Trip.jsx'
import InterestsButton from '@features/trip_plan/frontend/Interests.jsx'
import GuestsButton from '@features/guests/frontend/Guests.jsx'
import Compare from '@features/compare/frontend/Compare.jsx'
import CompareTray from '@features/compare/frontend/CompareTray.jsx'
import City from '@features/sights/frontend/City.jsx'
import Profile, { ProfileButton } from '@features/profile/frontend/Profile.jsx'

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
  // сервер не ответил на какой-то запрос — плашка «Временная ошибка» на 10 с, блоки продолжают работать
  const [down, setDown] = useState(false)
  useEffect(() => {
    let t
    const on = () => { setDown(true); clearTimeout(t); t = setTimeout(() => setDown(false), 10000) }
    addEventListener('api-down', on)
    return () => { removeEventListener('api-down', on); clearTimeout(t) }
  }, [])
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
  // место из «Что посмотреть рядом» в карточке отеля (features/sights)
  const [sight, setSight] = useState(null)
  // у открытого отеля показываем на карте найденное рядом: магазин, парк, аптеку…
  // без открытого отеля — место из «Жить рядом», к которому подбираем отели
  const pois = useMemo(() => {
    const r = result && (selected ? result.hotels.find(x => x.id === selected) : result.hotels[0])
    const pts = (r?.reasons || []).filter(x => x.point && (selected || x.lens.startsWith('sight_'))).map(x => x.point)
    if (sight && !pts.some(p => p.name === sight.name)) pts.push(sight)
    // «Жить рядом»: показать место и три лучших отеля — место может быть далеко за краем карты (Роза Хутор)
    const top = !selected && pts.length ? result.hotels.slice(0, 3).map(x => hotels.find(h => h.id === x.id)).filter(Boolean) : []
    return pts.length ? { type: 'FeatureCollection', features: pts.map(p => ({ type: 'Feature',
      properties: { name: p.name }, geometry: { type: 'Point', coordinates: [p.lon, p.lat] } })),
      fit: sight?.mode === 'car' ? [sight, hotels.find(h => h.id === selected)].filter(Boolean)
        : top.length ? [...pts, ...top] : null } : null
  }, [result, selected, sight, hotels])
  // места одного типа рядом с открытым отелем (клик по «Что рядом пешком»)
  const [places, setPlaces] = useState(null)
  // пеший маршрут на карте: до пляжа или до выбранного места
  const [route, setRoute] = useState(null)
  useEffect(() => { if (!selected) setCone(null); setPlaces(null); setRoute(null); setSight(null) }, [selected])
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
  const closeMapBox = () => { setPlaces(null); setRoute(null); setSight(null) }
  // пешком — маршрут по графу; дальше 40 минут — честно «на машине», точка на карте без пешей линии
  const showSight = r => {
    setPlaces(null); setSight(r)
    if (!r) setRoute(null)
    else if (r.mode === 'walk') showRoute(`/api/hotels/${selected}/route?lat=${r.lat}&lon=${r.lon}`, `До ${r.to}`)
    else setRoute({ title: `До ${r.to}`, none: true, note: `Пешком дальше 40 минут — на машине ≈ ${r.minutes} мин (оценка по прямой)` })
  }
  // «Жить рядом» на экране города: место становится фильтром подбора
  const liveNear = s => { setOn(prev => prev.includes(s.lens) ? prev : [...prev, s.lens]); setSelected(null) }

  // «Моя поездка»: #trip/<id брони>, на карте — отель брони
  const tripId = selected?.startsWith('trip/') ? selected.slice(5) : null
  const [tripHotel, setTripHotel] = useState(null)
  const mapSel = tripId ? tripHotel : selected
  const sel = useMemo(() => hotels.find(h => h.id === selected), [hotels, selected])
  // сравнение: #compare/<id>,<id>… — во всю ширину вместо списка и карты
  const compareIds = selected?.startsWith('compare/') ? selected.slice(8).split(',').filter(Boolean) : null
  const openCompare = ids => setSelected(`compare/${ids.join(',')}`)

  // «Научить О!кно»: новая характеристика описанием (#admin)
  if (selected === 'admin') return <AddCharacteristic onExit={() => setSelected(null)} />
  // «Для отелей»: экстранет отеля последней брони гостя (демо-поездки уже прошли — их не берём),
  // без брони — открытого отеля, иначе Pullman
  const openExtranet = () => api('/api/bookings').catch(() => []).then(list => {
    const last = list.filter(b => !b.finished_at).sort((a, b) => b.created_at.localeCompare(a.created_at))[0]
    setSelected(`extranet/${last?.hotel_id || sel?.id || 'w201474333'}`)
  })
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
          <span className="sg-city" role="button" title="Город и что посмотреть" onClick={() => setSelected('city')}><Icon name="pin" size={17} />Сочи</span>
          <span><Icon name="calendar" size={17} />{month === 5 ? '12–19 мая' : MONTH[month]}</span>
          <GuestsButton />
          <InterestsButton />
        </div>
        <ProfileButton onOpen={() => setSelected('profile')} selected={selected} />
        <button className="for-hotels" onClick={openExtranet}>Для отелей</button>
      </header>
      {down && <div className="temp-toast" role="alert">{TEMP_ERROR}<button onClick={() => setDown(false)} aria-label="Скрыть">×</button></div>}
      {selected === 'profile' ? <div className="main pf-main"><ErrorBoundary><Profile onExit={() => setSelected(null)} /></ErrorBoundary></div>
      : selected === 'city' ? <div className="main sg-main"><ErrorBoundary><City on={on} onLive={liveNear} onExit={() => setSelected(null)} /></ErrorBoundary></div>
      : compareIds ? <div className="main cmp-main"><ErrorBoundary resetKey={selected}><Compare ids={compareIds} lenses={lenses} on={on} month={month}
        onHotel={setSelected} onIds={openCompare} onExit={() => setSelected(null)} /></ErrorBoundary></div> : <>
      <div className="main">
        <aside className="panel"><ErrorBoundary resetKey={selected}>
          {error && <div className="chip warn">{error}</div>}
          {tripId
            ? <Trip bookingId={tripId} onHotel={setTripHotel} onExit={id => setSelected(id)} onRoute={r => { setPlaces(null); setRoute(r) }} routeShown={route?.title === 'Маршрут дня'} />
            : sel
            ? <HotelCard id={sel.id} month={month} onBack={() => setSelected(null)} onCone={setCone} onPlace={showPlaces} onBeach={showBeach}
              places={places} routeTitle={route?.title} nearMeta={nearMeta}
              sight={sight?.id} onSight={showSight} onCity={() => setSelected('city')} lenses={on} />
            : <SearchPanel hotels={hotels} lenses={lenses} on={on} setOn={setOn} month={month} setMonth={setMonth}
                result={result} onSelect={setSelected} />}
        </ErrorBoundary></aside>
        <section className="map"><ErrorBoundary>
          <HotelMap month={month} hotels={hotels} selected={mapSel} onSelect={setSelected} cone={route || places ? null : cone} fits={fits} pois={pois} places={places} route={route}
            onPlaceClick={routeTo} onCloseBox={closeMapBox} />
        </ErrorBoundary></section>
      </div>
      {!tripId && selected !== 'city' && selected !== 'profile' && <CompareTray hotels={hotels} onOpen={openCompare} />}
      </>}
    </div>
  )
}
