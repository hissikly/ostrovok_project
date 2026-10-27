import React, { useEffect, useState } from 'react'
import { api, post } from '@app/api.js'
import Icon from '@app/icons.jsx'
import Faq from '@features/knowledge/frontend/Faq.jsx'
import ConflictsPanel from '@features/conflicts/frontend/ConflictsPanel.jsx'
import HotelBookings from '@features/trip/frontend/HotelBookings.jsx'
import GuestReviews from '@features/profile/frontend/Reviews.jsx'

// Раздел Экстранета Островка «Что о вас знают гости» (макет — mockups/hotelier.html)
const NAV = [['calendar', 'Бронирования'], ['card', 'Цены и наличие'], ['building', 'Номера'],
  ['window', 'Условия'], ['mail', 'Сообщения'], ['star', 'Отзывы']]
const plural = (n, one, few, many) => {
  const m10 = n % 10, m100 = n % 100
  return m10 === 1 && m100 !== 11 ? one : m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20) ? few : many
}

// Поле «как мы поняли»: варианты — таблетками, числа и время — полем; отельер может поправить
function Field({ f, onChange }) {
  if (f.type === 'choice') {
    return <div className="pills">{f.options.map(o =>
      <button key={o} className={f.value === o ? 'on' : ''} onClick={() => onChange(f.value === o ? null : o)}>{o}</button>)}</div>
  }
  if (f.type === 'text') return <b>{f.value}</b>
  return <span className="ext-num">
    <input value={f.value ?? ''} placeholder="не сказано" onChange={e => onChange(e.target.value === '' ? null
      : f.type === 'number' ? Number(e.target.value.replace(/\D/g, '')) : e.target.value)} />
    {f.unit && <small>{f.unit}</small>}</span>
}

function Question({ q, hotelId, onDone }) {
  const [text, setText] = useState('')
  const [parsed, setParsed] = useState(null)
  const [done, setDone] = useState(null)
  const why = q.origin === 'agent' ? q.guest_text
    : `${q.demand} ${plural(q.demand, 'гость спрашивал', 'гостя спрашивали', 'гостей спрашивали')}`

  const send = async () => setParsed(await post(`/api/hotelier/${hotelId}/parse`, { question_id: q.id, text }))
  const save = async () => {
    const k = await post(`/api/hotelier/${hotelId}/answers`, { question_id: q.id, text, fields: parsed.fields.length ? parsed.fields : null })
    setDone(k.text); onDone()
  }
  const setField = (id, v) => setParsed(p => ({ ...p, fields: p.fields.map(f => f.id === id ? { ...f, value: v } : f) }))

  return (
    <div className={`ext-q ${done ? 'done' : ''}`}>
      <div className="ext-q-top">
        <div className="ext-ic"><Icon name={q.icon} /></div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="ext-q-t">{q.text}</div>
          <div className={`ext-demand ${q.origin === 'agent' ? 'agent' : ''}`}>
            <Icon name={q.origin === 'agent' ? 'sparkle' : 'users'} size={16} />{why}</div>
        </div>
      </div>
      {done
        ? <div className="ext-ok"><Icon name="check" size={18} />Готово. Гости уже видят: «{done}»</div>
        : !parsed
          ? <>
              <textarea value={text} onChange={e => setText(e.target.value)} placeholder="Ответьте своими словами, как удобно" />
              <div className="ext-actions">
                <button className="ext-btn pri" disabled={!text.trim()} onClick={send}>Отправить</button>
                <span className="muted" style={{ fontSize: 13 }}>Разложим ответ по полям и покажем, как поняли</span>
              </div>
            </>
          : <div className="ext-understood">
              <div className="ext-u-t"><Icon name="check" size={18} />Как мы поняли</div>
              {parsed.fields.length
                ? <div className="ext-fields">{parsed.fields.filter(f => f.type !== 'text').map(f =>
                    <React.Fragment key={f.id}><span>{f.label}</span><Field f={f} onChange={v => setField(f.id, v)} /></React.Fragment>)}
                  </div>
                : <div>{parsed.summary}</div>}
              <div className="ext-actions">
                <button className="ext-btn pri" onClick={save}>Всё верно</button>
                <button className="ext-btn sec" onClick={() => setParsed(null)}>Изменить ответ</button>
              </div>
            </div>}
    </div>
  )
}

function Known({ k, hotelId, onDone }) {
  const [edit, setEdit] = useState(null)
  const [state, setState] = useState(k.by_hotel ? 'Подтверждено отелем' : null)
  const [text, setText] = useState(k.text)
  const save = async t => {
    const r = await post(`/api/hotelier/${hotelId}/confirm`, { topic: k.topic, text: t })
    setText(r.text); setEdit(null); setState(t ? 'Уточнено отелем' : 'Подтверждено отелем'); onDone()
  }
  return (
    <div className="ext-fact">
      <div className="ext-ic"><Icon name={k.icon} /></div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="ext-q-t" style={{ fontSize: 15 }}>{k.question}</div>
        <div className="muted" style={{ fontSize: 14 }}>{text}</div>
        {edit !== null && <>
          <textarea value={edit} onChange={e => setEdit(e.target.value)} />
          <div className="ext-actions">
            <button className="ext-btn pri" onClick={() => save(edit)}>Сохранить</button>
            <button className="ext-btn sec" onClick={() => setEdit(null)}>Отмена</button>
          </div>
        </>}
      </div>
      {state
        ? <div className="ext-confirmed"><Icon name="check" size={16} />{state}</div>
        : edit === null && <div className="ext-fact-btns">
            <button className="yes" onClick={() => save(null)}>Верно</button>
            <button onClick={() => setEdit(text)}>Исправить</button>
          </div>}
    </div>
  )
}

export default function Extranet({ hotelId, hotels, onHotel, onExit }) {
  const [data, setData] = useState(null)
  const [tick, setTick] = useState(0)   // обновить превью гостя после ответа
  useEffect(() => { setData(null); api(`/api/hotelier/${hotelId}`).then(setData) }, [hotelId])
  const refresh = () => { setTick(t => t + 1); api(`/api/hotelier/${hotelId}`).then(d => setData(s => ({ ...s, demand: d.demand }))) }
  const pick = hotels.filter(h => h.okno).sort((a, b) => a.name.localeCompare(b.name, 'ru'))

  return (
    <div className="ext">
      <header className="hdr">
        <div className="logo">Островок!<span className="ext-logo-sub">Экстранет</span></div>
        <select className="ext-pick" value={hotelId} onChange={e => onHotel(e.target.value)}>
          {pick.map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
        </select>
        <button className="back" style={{ marginLeft: 8 }} onClick={onExit}>К поиску отелей</button>
      </header>
      <div className="ext-shell">
        <nav className="ext-nav">
          {NAV.map(([i, t]) => <a key={t}><Icon name={i} size={18} />{t}</a>)}
          <hr />
          <a className="on"><Icon name="sparkle" size={18} />Что о вас знают гости<span className="ext-new">новое</span></a>
        </nav>
        {!data ? <div className="ext-main muted">Загружаем…</div> : (
          <main className="ext-main">
            <div>
              <h1>Что о вас знают гости</h1>
              <div className="ext-stats">
                <div className="ext-stat hot"><b>{data.demand}</b><span>{plural(data.demand, 'гость ждёт', 'гостя ждут', 'гостей ждут')} ваших ответов</span></div>
                <div className="ext-stat"><b>{data.questions.length}</b><span>{plural(data.questions.length, 'вопрос', 'вопроса', 'вопросов')} от гостей и от нас</span></div>
                <div className="ext-stat"><b>{data.known.length}</b><span>{plural(data.known.length, 'факт', 'факта', 'фактов')} мы узнали сами</span></div>
              </div>
              <HotelBookings hotelId={hotelId} />
              <GuestReviews hotelId={hotelId} extranet />
              <ConflictsPanel key={`${hotelId}-${tick}`} hotelId={hotelId} onDone={refresh} />
              <section className="block">
                <h2>Вопросы от гостей</h2>
                {data.questions.length
                  ? data.questions.map(q => <Question key={q.id} q={q} hotelId={hotelId} onDone={refresh} />)
                  : <div className="muted" style={{ marginTop: 8 }}>Новых вопросов нет</div>}
              </section>
              <section className="block">
                <h2>Что мы о вас узнали сами</h2>
                {data.known.map(k => <Known key={k.topic} k={k} hotelId={hotelId} onDone={refresh} />)}
              </section>
            </div>
            <aside className="ext-aside">
              <div className="ext-cap">Так увидит гость</div>
              <Faq key={`${hotelId}-${tick}`} hotelId={hotelId} month={5} />
            </aside>
          </main>
        )}
      </div>
    </div>
  )
}
