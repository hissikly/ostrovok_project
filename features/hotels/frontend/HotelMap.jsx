import React, { useEffect, useRef } from 'react'
import * as maplibregl from 'maplibre-gl'
import workerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import DayRouteInfo, { OUTING_COLORS } from '@features/day/frontend/DayRoute.jsx'

maplibregl.setWorkerUrl(workerUrl)   // MapLibre 6 ищет воркер рядом с бандлом — Vite его туда сам не кладёт
const STYLE = 'https://tiles.openfreemap.org/styles/liberty'   // цветной стиль OpenFreeMap, без ключей
const SOCHI = [39.73, 43.585]
const RAY_COLOR = ['match', ['get', 'k'], 's', '#3D8BFD', '#CE2121']
const EMPTY = { type: 'FeatureCollection', features: [] }
const plural = (n, one, few, many) => {
  const m10 = n % 10, m100 = n % 100
  return m10 === 1 && m100 !== 11 ? one : m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20) ? few : many
}

// fits — результат подбора {id: 'all'|'some'|'unknown'|'none'}; без линз точки обычные
const FIT_COLOR = ['match', ['get', 'fit'], 'all', '#0E41D2', 'some', '#5B83F0', 'unknown', '#B5BBC7', 'none', '#D9DCE2', '#7F9BE6']
const SELECTED = '#FF6B1A'   // выбранный отель — тёплый акцент, не спорит с синим брендом и зелёными местами
// выходы из отеля (лента дня) — каждый своим цветом; обычный путь (o=0) — оранжевым
const OUTING_COLOR = ['match', ['%', ['-', ['coalesce', ['get', 'o'], 1], 1], OUTING_COLORS.length], 1, OUTING_COLORS[1], 2, OUTING_COLORS[2], 3, OUTING_COLORS[3], OUTING_COLORS[0]]
const FIT_RADIUS = ['match', ['get', 'fit'], 'all', 9, 'some', 6, 4]

const toGeo = (hotels, fits) => ({
  type: 'FeatureCollection',
  features: hotels.map(h => ({
    type: 'Feature',
    properties: { id: h.id, rich: h.okno ? 1 : 0, fit: fits ? fits[h.id] || 'none' : '' },
    geometry: { type: 'Point', coordinates: [h.lon, h.lat] },
  })),
})

// Путь словами: туда/обратно с подъёмом и то, что встретится по дороге
function RouteInfo({ r }) {
  if (r.none) return <div className="route-info"><b>{r.title}</b><span>Пешеходный путь не нашли</span></div>
  if (r.stops) return <DayRouteInfo r={r} />   // маршрут дня из «Ваш день здесь»
  const f = r.flags
  const notes = [
    f.steps > 0 && 'есть лестницы',
    f.underpass > 0 && 'подземный переход',
    f.bridge > 0 && 'мост или надземный переход',
    f.rail > 0 && 'переход через ж/д',
    f.major_m >= 100 && `${f.major_m} м вдоль большой дороги`,
  ].filter(Boolean)
  const dist = r.meters < 1000 ? `${r.meters} м` : `${(r.meters / 1000).toFixed(1).replace('.', ',')} км`
  return (
    <div className="route-info">
      <b>{r.title}</b>
      {/* туда: набор высоты = up_m; обратно в гору = то, что спустились по дороге туда (down_m) */}
      <div className="route-row"><span>Туда</span><b>{r.minutes} мин</b><i>{dist}{Math.max(r.up_m, r.down_m) < 5 ? '' : r.down_m >= r.up_m ? `, вниз ${r.down_m} м` : `, в гору ${r.up_m} м`}</i></div>
      <div className="route-row"><span>Обратно</span><b>{r.back_minutes} мин</b><i>{r.down_m >= 5 ? `в гору ${r.down_m} м` : 'почти ровно'}</i></div>
      {notes.length > 0 && <div className="route-notes">По пути: {notes.join(', ')}</div>}
    </div>
  )
}

// сколько моря в виде — словами и процентом, как на полоске в «О!кне»
const seaPart = s => s < 0.02 ? 'почти нет' : `${Math.max(1, Math.round(s * 100))}% вида`

export default function HotelMap({ hotels, selected, onSelect, cone, fits, pois, places, route, onPlaceClick, onCloseBox }) {
  const box = useRef(null)
  const map = useRef(null)
  const ready = useRef(false)
  // последние пропсы — чтобы применить их, когда карта догрузится
  const props = useRef({})
  props.current = { hotels, selected, cone, onSelect, fits, pois, places, route, onPlaceClick }

  // выбранный отель — оранжевый, крупнее и поверх всех; остальные — по подбору или «посчитано ли О!кно»
  const paintHotels = () => {
    const m = map.current, { fits, selected } = props.current
    const isSel = ['==', ['get', 'id'], selected || '']
    m.setPaintProperty('hotels', 'circle-color', ['case', isSel, SELECTED,
      fits ? FIT_COLOR : ['case', ['==', ['get', 'rich'], 1], '#0E41D2', '#7F9BE6']])
    m.setPaintProperty('hotels', 'circle-radius', ['case', isSel, 11,
      fits ? FIT_RADIUS : ['case', ['==', ['get', 'rich'], 1], 8, 5]])
    m.setPaintProperty('hotels', 'circle-stroke-width', ['case', isSel, 3, 2])
    m.setLayoutProperty('hotels', 'circle-sort-key', ['case', isSel, 10,
      fits ? ['match', ['get', 'fit'], 'all', 3, 'some', 2, 'unknown', 1, 0] : 0])
    m.setFilter('hotel-halo', ['==', ['get', 'id'], selected || ''])
  }
  const applyHotels = () => {
    const m = map.current, { hotels, fits } = props.current
    m.getSource('hotels').setData(toGeo(hotels, fits))
    paintHotels()
  }
  const applyCone = () => map.current.getSource('cone').setData(props.current.cone || EMPTY)
  const applyRoute = () => {
    const m = map.current, { route, places } = props.current
    const lines = route?.lines || (route?.coords ? [route.coords] : null)   // lines — выходы из отеля (лента дня)
    const c = lines?.flat()
    m.getSource('route').setData(lines ? { type: 'FeatureCollection', features: lines.map((l, i) => ({ type: 'Feature',
      properties: { o: route.lines ? i + 1 : 0 }, geometry: { type: 'LineString', coordinates: l } })) } : EMPTY)
    m.getSource('day-stops').setData({ type: 'FeatureCollection', features: (route?.stops || []).map(s => ({ type: 'Feature',
      properties: { n: String(s.n), name: s.name, o: s.outing }, geometry: { type: 'Point', coordinates: [s.lon, s.lat] } })) })
    if (c?.length && !places?.items?.length) {
      const b = new maplibregl.LngLatBounds(c[0], c[0])
      c.forEach(p => b.extend(p))
      m.fitBounds(b, { padding: { top: 180, bottom: 50, left: 50, right: 60 }, maxZoom: 17, duration: 800 })   // сверху плашка с минутами
    }
  }
  const applyPois = () => map.current.getSource('poi').setData(props.current.pois || EMPTY)
  const applyPlaces = () => {
    const m = map.current, { places, hotels, selected } = props.current
    const items = places?.items || []
    m.getSource('places').setData({ type: 'FeatureCollection', features: items.map((p, i) => ({ type: 'Feature',
      properties: { i, name: p.name || p.kind, label: `${p.walk_min} мин`, first: i === 0 ? 1 : 0 },
      geometry: { type: 'Point', coordinates: [p.lon, p.lat] } })) })
    const h = hotels.find(x => x.id === selected)
    if (items.length && h) {
      // показываем отель и все найденные места
      const b = new maplibregl.LngLatBounds([h.lon, h.lat], [h.lon, h.lat])
      items.forEach(p => b.extend([p.lon, p.lat]))
      m.fitBounds(b, { padding: { top: 180, bottom: 50, left: 50, right: 60 }, maxZoom: 17, duration: 800 })
    }
  }
  const applySelected = () => {
    const m = map.current, { selected, hotels } = props.current
    paintHotels()
    const h = hotels.find(x => x.id === selected)
    if (h) m.flyTo({ center: [h.lon, h.lat], zoom: Math.max(m.getZoom(), 15), speed: 1.4 })
  }

  useEffect(() => {
    const m = new maplibregl.Map({ container: box.current, style: STYLE, center: SOCHI, zoom: 12 })
    m.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right')
    m.on('load', () => {
      m.addSource('hotels', { type: 'geojson', data: EMPTY })
      m.addSource('cone', { type: 'geojson', data: EMPTY })
      m.addSource('poi', { type: 'geojson', data: EMPTY })
      m.addSource('places', { type: 'geojson', data: EMPTY })
      m.addSource('route', { type: 'geojson', data: EMPTY })
      m.addSource('day-stops', { type: 'geojson', data: EMPTY })
      m.addLayer({ id: 'cone', type: 'line', source: 'cone', filter: ['==', ['geometry-type'], 'LineString'],
        paint: { 'line-color': RAY_COLOR, 'line-width': 1.6, 'line-opacity': 0.75 } })
      // мягкое кольцо вокруг выбранного отеля
      m.addLayer({ id: 'hotel-halo', type: 'circle', source: 'hotels', filter: ['==', ['get', 'id'], ''],
        paint: { 'circle-radius': 22, 'circle-color': SELECTED, 'circle-opacity': 0.18,
          'circle-stroke-color': SELECTED, 'circle-stroke-width': 1.5, 'circle-stroke-opacity': 0.5 } })
      m.addLayer({ id: 'hotels', type: 'circle', source: 'hotels', paint: {
        'circle-radius': ['case', ['==', ['get', 'rich'], 1], 8, 5],
        'circle-color': ['case', ['==', ['get', 'rich'], 1], '#0E41D2', '#7F9BE6'],
        'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } })
      // найденное рядом с открытым отелем (фильтры «что рядом»)
      m.addLayer({ id: 'poi', type: 'circle', source: 'poi', paint: {
        'circle-radius': 7, 'circle-color': '#53AF24', 'circle-stroke-color': '#fff', 'circle-stroke-width': 2.5 } })
      m.addLayer({ id: 'route-casing', type: 'line', source: 'route', layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': '#fff', 'line-width': 8 } })
      m.addLayer({ id: 'route', type: 'line', source: 'route', layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: { 'line-color': OUTING_COLOR, 'line-width': 4.5 } })   // путь — цветом выбранного отеля: «от вашего отеля»
      // остановки маршрута дня — номера по порядку, как в ленте
      m.addLayer({ id: 'day-stops', type: 'circle', source: 'day-stops', paint: {
        'circle-radius': 11, 'circle-color': OUTING_COLOR, 'circle-stroke-color': '#fff', 'circle-stroke-width': 2.5 } })
      m.addLayer({ id: 'day-stops-n', type: 'symbol', source: 'day-stops', layout: {
        'text-field': ['get', 'n'], 'text-font': ['Noto Sans Bold'], 'text-size': 12, 'text-allow-overlap': true },
        paint: { 'text-color': '#fff' } })
      m.addLayer({ id: 'places', type: 'circle', source: 'places', paint: {
        'circle-radius': ['case', ['==', ['get', 'first'], 1], 9, 7], 'circle-color': '#53AF24',
        'circle-stroke-color': '#fff', 'circle-stroke-width': 2.5 } })
      m.addLayer({ id: 'places-label', type: 'symbol', source: 'places', layout: {
        'text-field': ['get', 'label'], 'text-font': ['Noto Sans Bold'], 'text-size': 12,
        'text-offset': [0, 1.3], 'text-anchor': 'top', 'text-allow-overlap': false },
        paint: { 'text-color': '#2E7D12', 'text-halo-color': '#fff', 'text-halo-width': 1.6 } })
      const tip = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10 })
      m.on('mouseenter', 'poi', e => tip.setLngLat(e.features[0].geometry.coordinates).setText(e.features[0].properties.name).addTo(m))
      m.on('mouseleave', 'poi', () => tip.remove())
      m.on('mouseenter', 'places', e => { m.getCanvas().style.cursor = 'pointer'
        tip.setLngLat(e.features[0].geometry.coordinates).setText(e.features[0].properties.name).addTo(m) })
      m.on('mouseleave', 'places', () => { m.getCanvas().style.cursor = ''; tip.remove() })
      // клик по месту — маршрут до него
      m.on('click', 'places', e => {
        const p = props.current.places?.items?.[e.features[0].properties.i]
        if (p) props.current.onPlaceClick(p)
      })
      // окно рисуем поверх точки отеля: белый кружок с синей обводкой
      m.addLayer({ id: 'eye', type: 'circle', source: 'cone', filter: ['==', ['get', 'k'], 'eye'],
        paint: { 'circle-radius': 6, 'circle-color': '#fff', 'circle-stroke-color': '#0E41D2', 'circle-stroke-width': 3 } })
      m.on('click', 'hotels', e => props.current.onSelect(e.features[0].properties.id))
      m.on('mouseenter', 'hotels', () => { m.getCanvas().style.cursor = 'pointer' })
      m.on('mouseleave', 'hotels', () => { m.getCanvas().style.cursor = '' })
      ready.current = true
      applyHotels(); applyCone(); applyPois(); applyPlaces(); applyRoute(); applySelected()
    })
    map.current = m
    return () => m.remove()
  }, [])

  useEffect(() => { if (ready.current) { applyHotels(); applySelected() } }, [hotels, fits])
  useEffect(() => { if (ready.current) applySelected() }, [selected])
  useEffect(() => { if (ready.current) applyCone() }, [cone])
  useEffect(() => { if (ready.current) applyPois() }, [pois])
  useEffect(() => { if (ready.current) applyPlaces() }, [places])
  useEffect(() => { if (ready.current) applyRoute() }, [route])

  const kinds = new Set((cone?.features || []).map(f => f.properties.k))
  return (
    <>
      <div ref={box} />
      {(places || route) && (
        <div className="map-places">
          {places && <>
            <b>{places.title}</b>
            <span>{places.items.length ? `${places.items.length} ${plural(places.items.length, 'место', 'места', 'мест')} до ${places.within_min} мин пешком. Нажмите на точку — проложим путь`
              : `На карте в ${places.within_min} мин пешком не нашли`}</span>
          </>}
          {route && <RouteInfo r={route} />}
          <button onClick={onCloseBox} aria-label="Скрыть">×</button>
        </div>
      )}
      {(kinds.size > 0 || pois) && (
        <div className="map-legend">
          {kinds.size > 0 && <>
            <div className="map-legend-title">Вид из окна</div>
            <div><b className="eye-dot" />окно номера</div>
            {kinds.has('s') && <div><i style={{ background: '#3D8BFD' }} />видно море{cone.share != null &&
              <span className="map-legend-share">{seaPart(cone.share)}</span>}</div>}
            {kinds.has('b') && <div><i style={{ background: '#CE2121' }} />закрывает дом</div>}
          </>}
          {pois && <div><b className="eye-dot" style={{ borderColor: '#53AF24', background: '#53AF24' }} />рядом, что вы искали</div>}
        </div>
      )}
    </>
  )
}
