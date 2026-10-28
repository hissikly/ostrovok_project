import React, { useEffect, useState } from 'react'
import { api, post } from '@app/api.js'
import Icon from '@app/icons.jsx'
import { guestsText } from '@features/guests/frontend/guests.js'
import { tripDates, plural } from '@features/trip/frontend/common.jsx'
import './profile.css'

const ANS = [['yes', 'Да'], ['no', 'Нет'], ['unsure', 'Не проверял']]
const ANS_WORD = { yes: 'Да', no: 'Нет', unsure: 'Не проверял' }

// Вопрос «Так и было?»: ответ сразу уходит на сервер, второй раз по тому же пункту не спрашиваем
function Question({ q, onAnswer, busy }) {
  return (
    <div className="pf-q">
      <div className="pf-q-ic"><Icon name={q.icon || 'check'} size={18} /></div>
      <div className="pf-q-body">
        <div className="t">{q.title}</div>
        {q.note && <div className="s">{q.note}</div>}
      </div>
      {q.answer
        ? <span className={`pf-ans ${q.answer}`}>{ANS_WORD[q.answer]}</span>
        : <div className="pills pf-pills">{ANS.map(([k, label]) =>
            <button key={k} className={k} disabled={busy} onClick={() => onAnswer(q.id, k)}>{label}</button>)}</div>}
    </div>
  )
}

function Stars({ value, onPick }) {
  const [hover, setHover] = useState(0)
  const shown = hover || value
  return (
    <div className="pf-stars" onMouseLeave={() => setHover(0)} role={onPick ? 'radiogroup' : undefined} aria-label="Оценка">
      {[1, 2, 3, 4, 5].map(n => onPick
        ? <button key={n} className={n <= shown ? 'on' : ''} onMouseEnter={() => setHover(n)} onClick={() => onPick(n)}
            role="radio" aria-checked={value === n} aria-label={`${n} из 5`}><Icon name="star" size={22} /></button>
        : <span key={n} className={n <= value ? 'on' : ''}><Icon name="star" size={18} /></span>)}
    </div>
  )
}

// Мнение об отеле своими словами: звёзды и текст, можно переписать
function Review({ t, onSaved }) {
  const r = t.review
  const [edit, setEdit] = useState(!r)
  const [stars, setStars] = useState(r?.stars || 0)
  const [text, setText] = useState(r?.text || '')
  const [busy, setBusy] = useState(false)
  const save = async () => {
    setBusy(true)
    try { onSaved(await post(`/api/profile/trips/${t.id}/review`, { stars, text })); setEdit(false) } finally { setBusy(false) }
  }
  if (!edit) return (
    <div className="pf-sec">
      <div className="pf-cap">Ваше мнение об отеле</div>
      <div className="pf-review">
        <Stars value={r.stars} />
        {r.text && <p>{r.text}</p>}
        <button className="pf-link" onClick={() => setEdit(true)}>Изменить</button>
      </div>
    </div>
  )
  return (
    <div className="pf-sec">
      <div className="pf-cap">Ваше мнение об отеле</div>
      <Stars value={stars} onPick={setStars} />
      <textarea className="pf-text" rows={3} maxLength={1000} value={text} onChange={e => setText(e.target.value)}
        placeholder="Что понравилось, что нет — своими словами" />
      <div className="pf-actions">
        <button className="tr-btn pri" disabled={!stars || busy} onClick={save}>Сохранить</button>
        {r && <button className="pf-link" onClick={() => { setEdit(false); setStars(r.stars); setText(r.text) }}>Отмена</button>}
      </div>
    </div>
  )
}

function TripCard({ t, onChange }) {
  const [busy, setBusy] = useState(false)
  const left = t.questions.filter(q => !q.answer)
  const [open, setOpen] = useState(left.length > 0)
  const answer = async (id, a) => {
    setBusy(true)
    try { onChange(await post(`/api/profile/trips/${t.id}/answers`, { answers: { [id]: a } })) } finally { setBusy(false) }
  }
  const finish = async () => {
    setBusy(true)
    try { onChange(await post(`/api/profile/trips/${t.id}/answers`, { answers: {} })); setOpen(true) } finally { setBusy(false) }
  }
  const promise = t.questions.filter(q => q.kind !== 'lens')
  const lens = t.questions.filter(q => q.kind === 'lens')
  const yes = t.questions.filter(q => q.answer === 'yes').length
  const no = t.questions.filter(q => q.answer === 'no').length
  return (
    <article className="block pf-trip">
      <div className="pf-head">
        <div>
          <h3><a href={`#${t.hotel.id}`}>{t.hotel.name}</a></h3>
          <div className="pf-meta">
            <span><Icon name="calendar" size={16} />{t.past ? t.when : tripDates(t.month)}</span>
            {t.guests && <span><Icon name="user" size={16} />{guestsText(t.guests)}</span>}
            {t.hotel.address && <span><Icon name="pin" size={16} />{t.hotel.address}</span>}
          </div>
        </div>
        <span className={`pf-badge ${t.past ? 'past' : ''}`}>{t.past ? 'Поездка прошла' : 'Предстоит'}</span>
      </div>

      {t.lenses.length > 0 && (
        <div className="pf-searched">
          <span>Вы искали:</span>
          {t.lenses.map(l => <span key={l.id} className="pf-chip"><Icon name={l.icon || 'check'} size={14} />{l.title}</span>)}
        </div>
      )}
      {t.wish && <div className="pf-wish"><b>Пожелание отелю:</b> {t.wish}
        <span className={`pf-status ${t.status}`}>{t.status_text}</span></div>}

      {!t.past ? (
        <div className="pf-actions">
          <a className="tr-btn sec pf-open" href={`#trip/${t.id}`}>Открыть поездку</a>
          <button className="pf-link" disabled={busy} onClick={finish}>Поездка завершена</button>
        </div>
      ) : <>
        <div className="pf-sec">
          <button className="pf-fold" onClick={() => setOpen(!open)} aria-expanded={open}>
            <span className="pf-cap">Так и было?</span>
            <span className="pf-progress">{left.length
              ? `Ответили на ${t.answered} из ${t.questions.length}`
              : no ? `Совпало ${yes} из ${yes + no}` : 'Всё совпало'}</span>
            <span className={`pf-arrow ${open ? 'open' : ''}`}>›</span>
          </button>
          {open && <>
            {promise.length > 0 && <div className="pf-group">Что мы обещали</div>}
            {promise.map(q => <Question key={q.id} q={q} onAnswer={answer} busy={busy} />)}
            {lens.length > 0 && <div className="pf-group">Подошёл ли отель под ваши фильтры</div>}
            {lens.map(q => <Question key={q.id} q={q} onAnswer={answer} busy={busy} />)}
            {!left.length && <div className="tr-thanks"><Icon name="check" size={20} />Спасибо! Ваши ответы уже в карточке отеля</div>}
          </>}
        </div>
        <Review key={t.id} t={t} onSaved={onChange} />
      </>}
    </article>
  )
}

// Профиль (#profile): поездки гостя — предстоящие и прошлые, «Так и было?» по обещанию и фильтрам, отзыв об отеле
export default function Profile({ onExit }) {
  const [p, setP] = useState(null)
  const [failed, setFailed] = useState(false)
  useEffect(() => { api('/api/profile').then(setP).catch(() => setFailed(true)) }, [])
  const replace = card => setP(prev => {
    const trips = prev.trips.map(t => t.id === card.id ? card : t)
    const past = trips.filter(t => t.past)
    return { trips: [...trips.filter(t => !t.past), ...past], summary: { ...prev.summary,
      past: past.length, answers: trips.reduce((s, t) => s + t.answered, 0),
      reviews: trips.filter(t => t.review).length,
      pending: past.filter(t => t.answered < t.questions.length).length } }
  })
  const up = p?.trips.filter(t => !t.past) || []
  const past = p?.trips.filter(t => t.past) || []
  const s = p?.summary
  return (
    <div className="pf">
      <button className="back" onClick={onExit}>← К отелям</button>
      <div className="pf-top">
        <div className="pf-ava"><Icon name="user" size={28} /></div>
        <div>
          <h1>Мои поездки</h1>
          {s && <div className="pf-sum">{s.trips} {plural(s.trips, 'поездка', 'поездки', 'поездок')}
            {s.answers > 0 && <> · {s.answers} {plural(s.answers, 'ответ', 'ответа', 'ответов')} «Так и было?»</>}
            {s.reviews > 0 && <> · {s.reviews} {plural(s.reviews, 'отзыв', 'отзыва', 'отзывов')}</>}</div>}
        </div>
      </div>
      {failed ? <div className="block">Не получилось загрузить поездки. Обновите страницу.</div>
      : !p ? <div className="muted">Загружаем…</div> : <>
        {up.length > 0 && <><h2 className="pf-h2">Предстоящие</h2>{up.map(t => <TripCard key={t.id} t={t} onChange={replace} />)}</>}
        {up.length === 0 && <div className="block pf-empty">Новых поездок пока нет. Выберите отель и забронируйте с пожеланием — поездка появится здесь.</div>}
        {past.length > 0 && <><h2 className="pf-h2">Прошлые поездки</h2>{past.map(t => <TripCard key={t.id} t={t} onChange={replace} />)}</>}
      </>}
    </div>
  )
}

// Кнопка в шапке: «Профиль» и точка, если после прошлой поездки остались вопросы
export function ProfileButton({ onOpen, selected }) {
  const [pending, setPending] = useState(0)
  useEffect(() => { api('/api/profile').then(x => setPending(x.summary.pending)).catch(() => {}) }, [selected])
  return (
    <button className="pf-btn" onClick={onOpen} title="Мои поездки">
      <span className="pf-btn-ic"><Icon name="user" size={18} />{pending > 0 && <i aria-label="Есть вопросы после поездки" />}</span>
      <span className="pf-btn-t">Профиль</span>
    </button>
  )
}
