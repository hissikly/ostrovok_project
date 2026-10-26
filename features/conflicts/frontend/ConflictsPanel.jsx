import React, { useEffect, useState } from 'react'
import { api, post } from '@app/api.js'
import Icon from '@app/icons.jsx'
import './conflicts.css'

// Экстранет: где ответ отеля расходится с открытыми данными. Гость видит обе версии,
// пока отель не примет расчёт или не объяснит свой ответ.
function Item({ c, hotelId, onDone }) {
  const [mode, setMode] = useState(null)   // null | 'explain'
  const [text, setText] = useState('')
  const [done, setDone] = useState(null)
  const act = async (action, t) => {
    await post(`/api/hotelier/${hotelId}/conflicts/${c.topic}`, { action, text: t })
    setDone(action === 'adopt' ? 'Исправили ответ: гости видят наш расчёт' : 'Пояснение сохранили: гости видят ваш ответ и пояснение')
    onDone()
  }
  if (c.status === 'explained' && !done) return null
  const site = c.kind === 'site'
  return (
    <div className="cf-ext">
      <div className="ext-q-t" style={{ display: 'flex', gap: 8, alignItems: 'center' }}><Icon name={c.icon} />{c.question}</div>
      <div className="cf" style={{ marginTop: 10 }}>
        <div className="cf-row"><span>{site ? 'На вашем сайте' : 'Ваш ответ'}</span>
          <span className="cf-v">«{c.hotel_text}»{site && c.site_url && <> <a href={c.site_url} target="_blank" rel="noreferrer">страница</a></>}</span></div>
        <div className="cf-row"><span>Открытые данные</span>{c.reason}</div>
      </div>
      {done
        ? <div className="ext-confirmed" style={{ marginTop: 10 }}><Icon name="check" size={16} />{done}</div>
        : mode === 'explain'
          ? <>
              <textarea placeholder="Например: на восточной стороне только служебные помещения, номеров там нет" value={text}
                onChange={e => setText(e.target.value)} />
              <div className="ext-actions">
                <button className="ext-btn pri" disabled={!text.trim()} onClick={() => act('explain', text)}>Сохранить пояснение</button>
                <button className="ext-btn sec" onClick={() => setMode(null)}>Отмена</button>
              </div>
            </>
          : <div className="ext-actions" style={{ marginTop: 10 }}>
              <button className="ext-btn pri" onClick={() => act('adopt')}>{site ? 'Расчёт верный — показывать гостям его' : 'Расчёт верный — поправить мой ответ'}</button>
              <button className="ext-btn sec" onClick={() => setMode('explain')}>{site ? 'На сайте верно — объяснить' : 'Мой ответ верный — объяснить'}</button>
            </div>}
    </div>
  )
}

export default function ConflictsPanel({ hotelId, onDone }) {
  const [items, setItems] = useState([])
  const load = () => api(`/api/hotels/${hotelId}/conflicts`).then(setItems).catch(() => setItems([]))
  useEffect(() => { load() }, [hotelId])
  const open = items.filter(c => c.status === 'open')
  if (!items.length) return null
  return (
    <section className="block">
      <h2>Гости видят, что мнения расходятся</h2>
      <p className="lead">Ваш ответ или текст на вашем сайте не совпал с тем, что мы посчитали по открытым данным. Пока не разберёмся, гости видят обе версии.</p>
      {open.length ? items.map(c => <Item key={c.topic} c={c} hotelId={hotelId} onDone={() => { onDone(); }} />)
        : <div className="muted">Всё разобрали, спасибо</div>}
    </section>
  )
}
