import React, { useEffect, useState } from 'react'
import { api, post } from '@app/api.js'
import Icon from '@app/icons.jsx'
import DayPanel from '@features/day/frontend/DayPanel.jsx'
import { useGuests, guestsText } from '@features/guests/frontend/guests.js'
import WishPicture from './WishPicture.jsx'
import { HowKnown, guestsWord, tripDates, NIGHTS } from './common.jsx'
import './trip.css'

// Строка с иконкой: по клику — откуда мы это знаем
function Row({ icon, title, note, facts, guests, kind = '' }) {
  const [open, setOpen] = useState(false)
  const toggle = () => setOpen(!open)
  return (
    <div className={`tr-row ${kind}`} onClick={toggle} tabIndex={0} aria-expanded={open}
      onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), toggle())}>
      <div className="tr-ic"><Icon name={icon} /></div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="t">{title}</div>
        {note && <div className="s">{note}</div>}
        {guests?.yes > 0 && <div className="tr-guests"><Icon name="users" size={14} />{guestsWord(guests.yes)}</div>}
        {open && facts?.length > 0 && <HowKnown facts={facts} guests={guests} />}
      </div>
    </div>
  )
}

function Status({ t }) {
  if (t.status === 'confirmed') return (
    <div className="tr-status ok"><Icon name="check" size={20} /><div><b>Отель подтвердил</b>
      {t.hotel_reply && <span className="tr-quote">«{t.hotel_reply}»</span>}</div></div>)
  if (t.status === 'declined') return (
    <div className="tr-status warn"><Icon name="mail" size={20} /><div><b>Отель ответил: всё выполнить не получится</b>
      {t.hotel_reply && <span className="tr-quote">«{t.hotel_reply}»</span>}</div></div>)
  return (
    <div className="tr-status"><Icon name="clock" size={20} /><div><b>Ждём ответа отеля на пожелание</b>
      <span>Номер уже ваш, а пожелание отель выполняет при заселении. Ответ появится здесь, обычно в течение дня</span></div></div>)
}

const GROUPS = [['bring', 'Взять с собой'], ['remind', 'Не забыть до поездки'], ['skip', 'Можно не брать']]

// kids — дети из «Гостей» в шапке (features/guests): тогда пометка «С ребёнком», переключать здесь нечего
function Packing({ items, kids }) {
  return (
    <div className="block">
      <div className="tr-pack-head">
        <h2>Чемодан</h2>
        {kids && <span className="tr-kids"><Icon name="child" size={16} />С ребёнком</span>}
      </div>
      <p className="lead">Только то, что следует из фактов об отеле и месте. Нажмите на вещь — расскажем почему.</p>
      {GROUPS.map(([k, name]) => {
        const xs = items.filter(x => x.kind === k)
        return xs.length > 0 && <React.Fragment key={k}>
          <div className="tr-group">{name}</div>
          {xs.map(x => <PackRow key={x.id} x={x} />)}
        </React.Fragment>
      })}
    </div>
  )
}

function PackRow({ x }) {
  const [open, setOpen] = useState(false)
  const toggle = () => setOpen(!open)
  return (
    <div className={`tr-row ${x.kind}`} onClick={toggle} tabIndex={0} aria-expanded={open}
      onKeyDown={e => (e.key === 'Enter' || e.key === ' ') && (e.preventDefault(), toggle())}>
      <div className="tr-ic"><Icon name={x.icon} /></div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="t">{x.item}</div>
        {open && <><div className="s">{x.why}</div><HowKnown facts={x.facts} /></>}
      </div>
    </div>
  )
}

const ANS = [['yes', 'Да'], ['no', 'Нет'], ['unsure', 'Не проверял']]

// «Так и было?»: после поездки — по тапу на каждый пункт обещания (и пожелание, если отель его подтвердил)
function Feedback({ t, onSent }) {
  const [started, setStarted] = useState(!!t.finished_at)
  const [ans, setAns] = useState({})
  const [sending, setSending] = useState(false)
  const qs = [...t.promise.map(p => ({ id: p.id, title: p.title })),
    ...(t.status === 'confirmed' ? [{ id: 'wish', title: `Номер по пожеланию: ${t.wish.text.toLowerCase()}` }] : [])]
  const done = qs.length > 0 && qs.every(q => t.answers[q.id])
  const pick = async (id, a) => {
    const next = { ...ans, [id]: a }
    setAns(next)
    if (qs.every(q => next[q.id] || t.answers[q.id]) && !sending) {
      setSending(true)
      await post(`/api/bookings/${t.id}/feedback`, { answers: next })
      await onSent()
      setSending(false)
    }
  }
  if (done) {
    const yes = qs.filter(q => t.answers[q.id] === 'yes').length
    return (
      <div className="block">
        <h2>Так и было?</h2>
        <div className="tr-thanks"><Icon name="check" size={20} />Спасибо! Ваши ответы уже в карточке отеля</div>
        <p className="lead" style={{ margin: 0 }}>{yes === qs.length ? 'Всё совпало с тем, что мы обещали.'
          : 'Где не совпало, мы стали осторожнее в обещаниях.'} Следующие гости увидят, что подтвердили вы и другие.</p>
      </div>
    )
  }
  if (!started) return (
    <div className="block">
      <h2>После поездки</h2>
      <p className="lead">Вернётесь — расскажите в три касания, так ли всё было. Это поможет следующим гостям.</p>
      <button className="tr-btn sec" onClick={async () => { setStarted(true); await post(`/api/bookings/${t.id}/feedback`, { answers: {} }) }}>
        Поездка завершена</button>
    </div>
  )
  return (
    <div className="block">
      <h2>Так и было?</h2>
      <p className="lead">Как прошла поездка в {t.hotel.name}? Отметьте каждый пункт.</p>
      {qs.map(q => {
        const a = ans[q.id] || t.answers[q.id]
        return (
          <div key={q.id} className="tr-q">
            <div className="t">{q.title}</div>
            <div className="pills">{ANS.map(([k, label]) =>
              <button key={k} className={`${a === k ? 'on' : ''} ${k}`} disabled={sending || !!t.answers[q.id]}
                onClick={() => pick(q.id, k)}>{label}</button>)}</div>
          </div>
        )
      })}
    </div>
  )
}

// «Моя поездка» (#trip/<id брони>): бронь с пожеланием и ответ отеля, что мы обещали, чемодан, весь день, «Так и было?».
// onHotel(id) — показать отель на карте; onRoute / routeShown — выходы из отеля на карте, как в карточке
export default function Trip({ bookingId, onHotel, onExit, onRoute, routeShown }) {
  const [t, setT] = useState(null)
  // «С ребёнком» — дети в «Гостях» шапки (features/guests): общие для чемодана, дня и шапки
  const [guests] = useGuests()
  const kids = guests.children.length > 0
  const [failed, setFailed] = useState(false)

  const load = () => api(`/api/bookings/${bookingId}?kids=${kids}`).then(x => { setT(x); onHotel?.(x.hotel_id) }).catch(() => setFailed(true))
  useEffect(() => { setT(null); setFailed(false) }, [bookingId])
  useEffect(() => { load() }, [bookingId, kids])
  // ждём ответа отеля: проверяем раз в несколько секунд, пока экран открыт
  useEffect(() => {
    if (t?.status !== 'sent') return
    const timer = setInterval(() => api(`/api/bookings/${bookingId}?kids=${kids}`).then(x => x.status !== 'sent' && setT(x)).catch(() => {}), 4000)
    return () => clearInterval(timer)
  }, [t?.status, bookingId, kids])

  if (failed) return (
    <div className="block">
      <button className="back" onClick={() => onExit(null)}>← Все отели</button>
      <p>Не нашли такую бронь. Возможно, ссылка устарела.</p>
    </div>
  )
  if (!t) return <div className="block muted">Открываем вашу поездку…</div>
  const view = { facade: t.facade, floor: t.floor }
  return (
    <div>
      <div className="block tr-head">
        <button className="back" onClick={() => onExit(t.hotel_id)}>← К отелю</button>
        <div><span className="tr-kicker">Моя поездка</span></div>
        <h1>{t.hotel.name}</h1>
        {t.hotel.address && <div className="info"><Icon name="pin" />{t.hotel.address}</div>}
        <div className="info"><Icon name="calendar" />{tripDates(t.month)}, {NIGHTS} ночей</div>
        <div className="info"><Icon name="user" />{guestsText(guests, true)}</div>
        <div className="tr-booked"><Icon name="check" size={18} />Номер забронирован</div>
      </div>

      <div className="block">
        <h2>Пожелание к номеру</h2>
        {t.wish.items.length
          ? <>
              <div className="tr-plate">
                <WishPicture facade={t.facade} floor={t.floor} levels={t.hotel.levels} items={t.wish.items} />
                <div className="tr-plate-text"><small>Отелю отправили</small>{t.wish.text}</div>
              </div>
              {t.wish.items.map(it => <Row key={it.id} icon={{ side: 'window', floor: 'building', quiet: 'mute' }[it.id] || 'check'}
                title={it.text} note={it.reason} facts={it.facts} />)}
            </>
          : <p className="lead">Без особых пожеланий: подойдёт любой номер этой категории.</p>}
        <Status t={t} />
      </div>

      {t.promise.length > 0 && (
        <div className="block">
          <h2>Что мы вам обещали</h2>
          <p className="lead">На этом держался ваш выбор. После поездки спросим, так ли было.</p>
          {t.promise.map(p => <Row key={p.id} icon={p.icon} title={p.title} note={p.note} facts={p.facts} guests={p.guests} />)}
        </div>
      )}

      {t.packing.length > 0 && <Packing items={t.packing} kids={kids} />}

      <DayPanel hotelId={t.hotel_id} month={t.month} view={view} onRoute={onRoute} routeShown={routeShown} />

      <Feedback key={t.id} t={t} onSent={load} />
    </div>
  )
}
