import React, { useEffect, useState } from 'react'
import { api } from '@app/api.js'
import Icon from '@app/icons.jsx'
import './conflicts.css'

// Темы «Что важно знать» → темы базы знаний, по которым сверяем ответ отеля и расчёт
export const ROW_TOPIC = { sea: 'sea_view', beach: 'beach' }

// Гость видит обе версии, пока отель не поправит ответ или не объяснит его
export function ConflictNote({ c, compact }) {
  if (!c) return null
  // в «Что важно знать» расчёт уже показан строкой выше — достаточно версии отеля
  if (compact && c.status === 'open') {
    return (
      <div className="cf" onClick={e => e.stopPropagation()}>
        <div className="cf-t"><Icon name="question" size={16} />Отель пишет иначе</div>
        «{c.hotel_text}». {c.reason}. Уточняем у отеля
      </div>
    )
  }
  if (compact && c.status === 'explained') {
    return <div className="cf cf-explained" onClick={e => e.stopPropagation()}><span>Отель пояснил: {lower(c.explanation)}</span></div>
  }
  if (c.status === 'explained') {
    return (
      <div className="cf cf-explained" onClick={e => e.stopPropagation()}>
        <b>Отель пояснил</b>{c.explanation}
        <span>По открытым данным выходило иначе: {lower(c.reason)}</span>
      </div>
    )
  }
  return (
    <div className="cf" onClick={e => e.stopPropagation()}>
      <div className="cf-t"><Icon name="question" size={16} />Мнения расходятся</div>
      <div className="cf-row"><span>{c.kind === 'site' ? 'Сайт отеля' : 'Отель'}</span>
        <span className="cf-v">«{c.hotel_text}»{c.site_url && <> <a href={c.site_url} target="_blank" rel="noreferrer">открыть страницу</a></>}</span></div>
      <div className="cf-row"><span>Наш расчёт</span>{c.computed_text}</div>
      <div className="cf-foot">Уточняем у отеля. Пока ответа нет, советуем проверить при бронировании</div>
    </div>
  )
}

function lower(s) {
  return s ? s[0].toLowerCase() + s.slice(1) : ''
}

// Список расхождений отеля (для «Что важно знать»): topic → расхождение
export function useConflicts(hotelId) {
  const [byTopic, setByTopic] = useState({})
  useEffect(() => {
    if (!hotelId) return
    setByTopic({})
    api(`/api/hotels/${hotelId}/conflicts`)
      .then(cs => setByTopic(Object.fromEntries(cs.map(c => [c.topic, c])))).catch(() => {})
  }, [hotelId])
  return byTopic
}
