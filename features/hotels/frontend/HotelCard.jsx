import React, { useEffect, useState } from 'react'
import { api } from '@app/api.js'
import Icon from '@app/icons.jsx'
import FactList from '@features/facts/frontend/FactList.jsx'
import WindowPanel from '@features/okno/frontend/WindowPanel.jsx'

function ratingWord(r) {
  return r >= 9 ? 'Превосходно' : r >= 8.5 ? 'Отлично' : r >= 8 ? 'Очень хорошо' : 'Хорошо'
}

export default function HotelCard({ id, onBack, onCone }) {
  const [h, setH] = useState(null)
  const [facts, setFacts] = useState([])

  useEffect(() => {
    setH(null); setFacts([])
    api(`/api/hotels/${id}`).then(setH)
    api(`/api/hotels/${id}/facts`).then(setFacts)
  }, [id])

  if (!h) return <div className="block muted">Загружаем…</div>
  const elev = facts.find(f => f.characteristic === 'elevation')
  return (
    <div>
      <div className="block">
        <button className="back" onClick={onBack}>← Все отели</button>
        <h1>{h.name}</h1>
        <div className="rating"><b>{h.mock.rating.toFixed(1).replace('.', ',')}</b>{ratingWord(h.mock.rating)}
          <span>{h.mock.reviews} отзывов</span></div>
        {h.address && <div className="info"><Icon name="pin" />{h.address}</div>}
        {elev && <div className="info"><Icon name="mountain" />{elev.value.meters} м над уровнем моря</div>}
        <div className="chips">
          <span className="chip">{h.kind_ru}</span>
          {h.stars && <span className="chip">{'★'.repeat(h.stars)}</span>}
          {h.levels && <span className="chip"><Icon name="building" size={16} />{h.levels} этажей</span>}
        </div>
        <div className="price"><b>{h.mock.price_rub.toLocaleString('ru-RU')} ₽</b><small>за ночь</small><span className="chip" style={{ padding: '2px 9px', fontSize: 12, color: 'var(--muted)' }}>демо-цена</span></div>
      </div>
      <WindowPanel hotelId={id} onCone={onCone} />
      <FactList facts={facts.filter(f => f.characteristic !== 'elevation')} />
    </div>
  )
}
