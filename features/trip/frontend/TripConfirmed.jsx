import React, { useState } from 'react'
import Icon from '@app/icons.jsx'
import { guestsWord, plural } from './common.jsx'
import './trip.css'

// Строка в «Что важно знать»: что подтвердили гости после поездки («Так и было?»).
// facts — факты отеля, отсюда берём наблюдения guest_feedback (features/trip)
export default function TripConfirmed({ facts }) {
  const [open, setOpen] = useState(false)
  const fb = facts.filter(f => f.characteristic === 'guest_feedback' && f.value.yes > 0)
  if (!fb.length) return null
  const demo = fb.reduce((s, f) => s + f.value.demo, 0)
  const all = fb.reduce((s, f) => s + f.value.guests, 0)
  return (
    <div className="fact" onClick={() => setOpen(!open)}>
      <div className="ic"><Icon name="users" /></div>
      <div style={{ flex: 1 }}>
        <div className="t">Гости проверили на себе</div>
        <div className="sides tr-confirmed">{fb.map(f =>
          <div key={f.id}><span>{f.value.label}</span><b>{guestsWord(f.value.yes)}</b></div>)}</div>
        {open && <div className="how">Мы спрашиваем гостей после поездки, так ли было то, что мы обещали. «Да» делает нас увереннее,
          «нет» — осторожнее и уходит вопросом отелю. {demo > 0 && `Из ${all} ${plural(all, 'ответа', 'ответов', 'ответов')} ${demo} — демо для показа.`}</div>}
      </div>
    </div>
  )
}
