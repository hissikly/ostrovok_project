import React, { useEffect, useRef } from 'react'
import maplibregl from 'maplibre-gl'

const STYLE = 'https://tiles.openfreemap.org/styles/liberty'   // цветной стиль OpenFreeMap, без ключей
const SOCHI = [39.73, 43.585]
const RAY_COLOR = ['match', ['get', 'k'], 's', '#3D8BFD', '#CE2121']
const EMPTY = { type: 'FeatureCollection', features: [] }

// fits — результат подбора {id: 'all'|'some'|'unknown'|'none'}; без линз точки обычные
const FIT_COLOR = ['match', ['get', 'fit'], 'all', '#0E41D2', 'some', '#5B83F0', 'unknown', '#B5BBC7', 'none', '#D9DCE2', '#7F9BE6']
const FIT_RADIUS = ['match', ['get', 'fit'], 'all', 9, 'some', 6, 4]

const toGeo = (hotels, fits) => ({
  type: 'FeatureCollection',
  features: hotels.map(h => ({
    type: 'Feature',
    properties: { id: h.id, rich: h.okno ? 1 : 0, fit: fits ? fits[h.id] || 'none' : '' },
    geometry: { type: 'Point', coordinates: [h.lon, h.lat] },
  })),
})

export default function HotelMap({ hotels, selected, onSelect, cone, fits, pois }) {
  const box = useRef(null)
  const map = useRef(null)
  const ready = useRef(false)
  // последние пропсы — чтобы применить их, когда карта догрузится
  const props = useRef({})
  props.current = { hotels, selected, cone, onSelect, fits, pois }

  const applyHotels = () => {
    const m = map.current, { hotels, fits } = props.current
    m.getSource('hotels').setData(toGeo(hotels, fits))
    m.setPaintProperty('hotels', 'circle-color', fits ? FIT_COLOR : ['case', ['==', ['get', 'rich'], 1], '#0E41D2', '#7F9BE6'])
    // подходящие — поверх остальных
    m.setLayoutProperty('hotels', 'circle-sort-key', fits ? ['match', ['get', 'fit'], 'all', 3, 'some', 2, 'unknown', 1, 0] : 0)
  }
  const applyCone = () => map.current.getSource('cone').setData(props.current.cone || EMPTY)
  const applyPois = () => map.current.getSource('poi').setData(props.current.pois || EMPTY)
  const applySelected = () => {
    const m = map.current, { selected, hotels } = props.current
    m.setPaintProperty('hotels', 'circle-radius',
      ['case', ['==', ['get', 'id'], selected || ''], 11, props.current.fits ? FIT_RADIUS : ['case', ['==', ['get', 'rich'], 1], 8, 5]])
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
      m.addLayer({ id: 'cone', type: 'line', source: 'cone', filter: ['==', ['geometry-type'], 'LineString'],
        paint: { 'line-color': RAY_COLOR, 'line-width': 1.6, 'line-opacity': 0.75 } })
      m.addLayer({ id: 'hotels', type: 'circle', source: 'hotels', paint: {
        'circle-radius': ['case', ['==', ['get', 'rich'], 1], 8, 5],
        'circle-color': ['case', ['==', ['get', 'rich'], 1], '#0E41D2', '#7F9BE6'],
        'circle-stroke-color': '#fff', 'circle-stroke-width': 2 } })
      // найденное рядом с открытым отелем (фильтры «что рядом»)
      m.addLayer({ id: 'poi', type: 'circle', source: 'poi', paint: {
        'circle-radius': 7, 'circle-color': '#53AF24', 'circle-stroke-color': '#fff', 'circle-stroke-width': 2.5 } })
      const tip = new maplibregl.Popup({ closeButton: false, closeOnClick: false, offset: 10 })
      m.on('mouseenter', 'poi', e => tip.setLngLat(e.features[0].geometry.coordinates).setText(e.features[0].properties.name).addTo(m))
      m.on('mouseleave', 'poi', () => tip.remove())
      // окно рисуем поверх точки отеля: белый кружок с синей обводкой
      m.addLayer({ id: 'eye', type: 'circle', source: 'cone', filter: ['==', ['get', 'k'], 'eye'],
        paint: { 'circle-radius': 6, 'circle-color': '#fff', 'circle-stroke-color': '#0E41D2', 'circle-stroke-width': 3 } })
      m.on('click', 'hotels', e => props.current.onSelect(e.features[0].properties.id))
      m.on('mouseenter', 'hotels', () => { m.getCanvas().style.cursor = 'pointer' })
      m.on('mouseleave', 'hotels', () => { m.getCanvas().style.cursor = '' })
      ready.current = true
      applyHotels(); applyCone(); applyPois(); applySelected()
    })
    map.current = m
    return () => m.remove()
  }, [])

  useEffect(() => { if (ready.current) { applyHotels(); applySelected() } }, [hotels, fits])
  useEffect(() => { if (ready.current) applySelected() }, [selected])
  useEffect(() => { if (ready.current) applyCone() }, [cone])
  useEffect(() => { if (ready.current) applyPois() }, [pois])

  const kinds = new Set((cone?.features || []).map(f => f.properties.k))
  return (
    <>
      <div ref={box} />
      {(kinds.size > 0 || pois) && (
        <div className="map-legend">
          {kinds.size > 0 && <>
            <div className="map-legend-title">Вид из окна</div>
            <div><b className="eye-dot" />окно номера</div>
            {kinds.has('s') && <div><i style={{ background: '#3D8BFD' }} />видно море</div>}
            {kinds.has('b') && <div><i style={{ background: '#CE2121' }} />закрывает дом</div>}
          </>}
          {pois && <div><b className="eye-dot" style={{ borderColor: '#53AF24', background: '#53AF24' }} />рядом, что вы искали</div>}
        </div>
      )}
    </>
  )
}
