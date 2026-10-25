import React, { useEffect, useMemo, useState } from 'react'
import { api, post } from './api.js'
import Icon from './icons.jsx'
import HotelMap from '@features/hotels/frontend/HotelMap.jsx'
import SearchPanel from '@features/search/frontend/SearchPanel.jsx'
import HotelCard from '@features/hotels/frontend/HotelCard.jsx'

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
  const fits = useMemo(() => result && Object.fromEntries(result.hotels.map(r => [r.id, r.fit])), [result])
  useEffect(() => { if (!selected) setCone(null) }, [selected])

  const sel = useMemo(() => hotels.find(h => h.id === selected), [hotels, selected])

  return (
    <div className="layout">
      <header className="hdr">
        <div className="logo">Островок!</div>
        <span className="chip lime">О!кно</span>
        <div className="trip">
          <span><Icon name="pin" size={17} />Сочи</span>
          <span><Icon name="calendar" size={17} />{month === 5 ? '12–19 мая' : MONTH[month]}</span>
          <span><Icon name="user" size={17} />2 взрослых</span>
        </div>
      </header>
      <div className="main">
        <aside className="panel">
          {error && <div className="chip warn">{error}</div>}
          {sel
            ? <HotelCard id={sel.id} onBack={() => setSelected(null)} onCone={setCone} />
            : <SearchPanel hotels={hotels} lenses={lenses} on={on} setOn={setOn} setMonth={setMonth}
                result={result} onSelect={setSelected} />}
        </aside>
        <section className="map">
          <HotelMap hotels={hotels} selected={selected} onSelect={setSelected} cone={cone} fits={fits} />
        </section>
      </div>
    </div>
  )
}
