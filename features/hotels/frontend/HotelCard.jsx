import React, { useEffect, useState } from 'react'
import { api } from '@app/api.js'
import Icon from '@app/icons.jsx'
import FactList from '@features/facts/frontend/FactList.jsx'
import DayPanel from '@features/day/frontend/DayPanel.jsx'
import Faq from '@features/knowledge/frontend/Faq.jsx'
import WindowPanel from '@features/okno/frontend/WindowPanel.jsx'
import AgentFacts from '@features/characteristics/frontend/AgentFacts.jsx'
import BookBox from '@features/trip/frontend/BookBox.jsx'
import TripConfirmed from '@features/trip/frontend/TripConfirmed.jsx'
import CompareButton from '@features/compare/frontend/CompareButton.jsx'

function ratingWord(r) {
  return r >= 9 ? 'Превосходно' : r >= 8.5 ? 'Отлично' : r >= 8 ? 'Очень хорошо' : 'Хорошо'
}

export default function HotelCard({ id, month, onBack, onCone, onPlace, onBeach, onDayRoute, places, routeTitle, nearMeta }) {
  const [h, setH] = useState(null)
  const [facts, setFacts] = useState([])
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)
  const [view, setView] = useState(null)   // сторона и этаж из «О!кна»

  useEffect(() => {
    setH(null); setFacts([]); setFailed(false); setView(null)
    api(`/api/hotels/${id}`).then(setH).catch(() => setFailed(true))
    api(`/api/hotels/${id}/facts`).then(setFacts).catch(() => setFacts([]))
  }, [id, attempt])

  if (failed) return (
    <div className="block">
      <button className="back" onClick={onBack}>← Все отели</button>
      <p style={{ margin: '8px 0 12px' }}>Не получилось загрузить отель — похоже, пропала связь с сервером.</p>
      <button className="pills-retry" onClick={() => setAttempt(a => a + 1)}>Повторить</button>
    </div>
  )
  if (!h) return <div className="block muted">Загружаем…</div>
  const elev = facts.find(f => f.characteristic === 'elevation')
  // ответы гостей «Так и было?» (features/trip): своей строкой и сдвигом уверенности исходных фактов
  const fb = Object.fromEntries(facts.filter(f => f.characteristic === 'guest_feedback').map(f => [f.value.fact_id, f.value.confidence]))
  const shown = facts.filter(f => f.characteristic !== 'guest_feedback').map(f => fb[f.id] ? { ...f, confidence: fb[f.id] } : f)
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
          {h.stars && <span className="chip" title={h.stars_mock ? 'В открытых данных категории нет — показываем демо, как цену' : 'Категория из OpenStreetMap'}>
            <span style={{ color: '#FFB800' }}>{'★'.repeat(h.stars)}</span>{h.stars_mock && <span className="muted">демо</span>}</span>}
          {h.levels && <span className="chip"><Icon name="building" size={16} />{h.levels} этажей</span>}
        </div>
        <div className="price"><b>{h.mock.price_rub.toLocaleString('ru-RU')} ₽</b><small>за ночь</small><span className="chip" style={{ padding: '2px 9px', fontSize: 12, color: 'var(--muted)' }}>демо-цена</span>
          <span style={{ marginLeft: 'auto' }}><CompareButton id={h.id} /></span></div>
      </div>
      <WindowPanel key={id} hotelId={id} onCone={onCone} onPick={setView} />
      <BookBox hotelId={id} view={view} month={month} price={h.mock.price_rub} />
      <FactList facts={shown.filter(f => f.characteristic !== 'elevation' && !f.evidence?.agent)} activePlace={places?.spec}
        onPlace={onPlace} onBeach={onBeach} beachOn={routeTitle === 'До пляжа'} nearMeta={nearMeta}>
        <AgentFacts inline hotelId={id} onPlace={onPlace} activePlace={places?.spec}
          skip={facts.filter(f => f.characteristic.startsWith('web:')).map(f => f.characteristic.slice(4))} />
        <TripConfirmed facts={facts} />
      </FactList>
      <DayPanel brief hotelId={id} month={month} view={view} onRoute={onDayRoute} routeShown={routeTitle === 'Маршрут дня'} />
      <Faq hotelId={id} month={month} />
    </div>
  )
}
