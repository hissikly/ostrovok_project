import React, { useEffect, useState } from 'react'
import { api, post } from '@app/api.js'
import Icon from '@app/icons.jsx'
import { ConflictNote } from '@features/conflicts/frontend/ConflictNote.jsx'
import { AgentSearching, AgentTrace, SiteQuote } from '@features/web_sources/frontend/SiteQuote.jsx'

const ASK_HINT = 'Обычно отвечают за 1–3 дня'

// Спросить у отеля: вопрос встаёт в очередь отельеру; если его уже задавали — растёт счётчик гостей
function AskHotel({ hotelId, topic, text, asked, onAsked }) {
  const [busy, setBusy] = useState(false)
  if (asked) {
    return <div className="faq-asked"><Icon name="check" size={16} />Спросили у отеля. Ответ появится здесь
      {asked.demand > 1 && <span>, этим интересуются ещё {asked.demand - 1}</span>}</div>
  }
  const send = async () => {
    setBusy(true)
    try { onAsked(await post(`/api/hotelier/${hotelId}/questions`, { topic, text })) } finally { setBusy(false) }
  }
  return <button className="faq-ask-btn" disabled={busy} onClick={send}>Спросить у отеля</button>
}

function Answer({ a, hotelId, asked, onAsked }) {
  const [open, setOpen] = useState(false)
  if (a.status !== 'answered') {
    return (
      <div className="faq-row unknown">
        <div className="fq">{a.question}</div>
        <div className="fa">Этого мы пока не знаем :(</div>
        {a.can_ask_hotel && <AskHotel hotelId={hotelId} topic={a.topic} asked={asked[a.topic]} onAsked={onAsked} />}
      </div>
    )
  }
  return (
    <div className="faq-row" onClick={() => setOpen(!open)}>
      <div className="fq">{a.question}</div>
      {a.conflict?.status === 'open'
        ? <ConflictNote c={a.conflict} />
        : <div className="fa">{a.text}</div>}
      {a.conflict?.status === 'explained' && <ConflictNote c={a.conflict} />}
      {open && a.conflict?.status !== 'open' && <div className="faq-note">{a.note}</div>}
      {open && a.level === 'web' && <SiteQuote quote={a.quote} url={a.url} date={a.obtained_at} />}
    </div>
  )
}

export default function Faq({ hotelId, month }) {
  const [items, setItems] = useState([])
  const [asked, setAsked] = useState({})        // topic | текст вопроса → вопрос в очереди
  const [q, setQ] = useState('')
  const [reply, setReply] = useState(null)       // ответ на вопрос из поля
  const [busy, setBusy] = useState(false)         // агент ищет ответ (сайт отеля с моделью — до нескольких секунд)

  useEffect(() => {
    setItems([]); setReply(null); setQ('')
    api(`/api/hotels/${hotelId}/faq${month ? `?month=${month}` : ''}`).then(setItems)
    api(`/api/hotelier/${hotelId}/questions`)
      .then(qs => setAsked(Object.fromEntries(qs.map(x => [x.topic || x.key, x])))).catch(() => {})
  }, [hotelId, month])

  const onAsked = qn => setAsked(s => ({ ...s, [qn.topic || qn.key]: qn }))
  const submit = async e => {
    e.preventDefault()
    if (!q.trim() || busy) return
    setReply(null)
    setBusy(true)
    try {
      setReply({ question: q.trim(), ...(await post(`/api/hotels/${hotelId}/ask`, { text: q, month })) })
    } finally { setBusy(false) }
  }

  // в списке — только то, на что есть ответ; остальное гость спросит сам в поле выше
  const known = items.filter(a => a.status === 'answered')
  return (
    <div className="block">
      <h2>Частые вопросы</h2>
      <form className="describe faq-input" onSubmit={submit}>
        <Icon name="sparkle" />
        <input placeholder="Спросить об отеле" value={q} onChange={e => { setQ(e.target.value); if (!e.target.value) setReply(null) }} />
        {q.trim() && <button className="go" disabled={busy}>Спросить</button>}
      </form>

      {busy && <AgentSearching />}

      {reply && (
        <div className="faq-reply">
          {reply.status === 'no_topic'
            ? <div className="faq-row unknown">
                <div className="fq">{reply.question}</div>
                <div className="fa">Этого мы пока не знаем :( Спросить у отеля? {ASK_HINT}</div>
                <AskHotel hotelId={hotelId} text={reply.question} asked={null} onAsked={qn => { onAsked(qn); setReply({ ...reply, askedQ: qn }) }} />
                {reply.askedQ && <div className="faq-asked"><Icon name="check" size={16} />Спросили у отеля. Ответ появится здесь</div>}
              </div>
            : reply.answers.map(a => a.status === 'answered'
              ? <Answer key={a.topic} a={a} hotelId={hotelId} asked={asked} onAsked={onAsked} />
              : <div key={a.topic} className="faq-row unknown">
                  <div className="fq">{a.question}</div>
                  <div className="fa">Этого мы пока не знаем :( {a.can_ask_hotel ? `Спросить у отеля? ${ASK_HINT}` : ''}</div>
                  {a.can_ask_hotel && <AskHotel hotelId={hotelId} topic={a.topic} asked={asked[a.topic]} onAsked={onAsked} />}
                </div>)}
          <AgentTrace steps={reply.trace} />
        </div>
      )}

      {known.map(a => <Answer key={a.topic} a={a} hotelId={hotelId} asked={asked} onAsked={onAsked} />)}
    </div>
  )
}
