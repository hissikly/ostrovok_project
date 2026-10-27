import React, { useEffect, useState } from 'react'
import { api } from '@app/api.js'
import Icon from '@app/icons.jsx'
import './sights.css'

// «Что посмотреть рядом» в карточке отеля: три ближайших места из подборки города
export default function SightsNearby({ hotelId, active, onShow, onCity }) {
  const [rows, setRows] = useState(null)
  useEffect(() => {
    setRows(null)
    api(`/api/hotels/${hotelId}/sights`).then(setRows).catch(() => setRows([]))
  }, [hotelId])
  if (!rows?.length) return null
  return (
    <div className="block sg-near">
      <h2>Что посмотреть рядом</h2>
      {rows.map(r => (
        <div key={r.id} className={`sg-near-row ${active === r.id ? 'on' : ''}`} onClick={() => onShow(active === r.id ? null : r)}>
          <img src={`/api/sights/${r.id}/photo.jpg`} alt="" />
          <div><b>{r.name}</b><span>{r.tags.join(' · ')}</span></div>
          <i><Icon name={r.mode === 'walk' ? 'walk' : 'car'} size={16} />{r.mode === 'walk' ? `${r.minutes} мин` : `≈ ${r.minutes} мин`}</i>
        </div>
      ))}
      <button className="back" onClick={onCity}>Вся подборка Сочи →</button>
    </div>
  )
}
