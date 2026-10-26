import React from 'react'
import Icon from '@app/icons.jsx'
import './web_sources.css'

const ICON = { pool: 'waves', own_beach: 'beach', kitchen: 'fork', wifi: 'bolt', lift: 'building', quiet_rooms: 'mute' }
// темы сайта без своего вопроса в «Частых вопросах»; остальные отвечают там, sea_view и beach_claim сверяет conflicts
export const SITE_ROW = Object.keys(ICON)

const host = url => { try { return new URL(url).hostname.replace(/^www\./, '') } catch { return '' } }
const day = iso => iso ? new Date(iso).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long' }) : ''

// Дословная цитата с сайта отеля и ссылка на страницу, где она написана
export function SiteQuote({ quote, url, date }) {
  if (!quote) return null
  return (
    <div className="site-quote" onClick={e => e.stopPropagation()}>
      <div className="q">«{quote.replace(/[.;,]$/, '')}»</div>
      <a href={url} target="_blank" rel="noreferrer">{host(url)}</a>
      {date && <span>, проверили {day(date)}</span>}
    </div>
  )
}

// Строка «С сайта отеля» в «Что важно знать»: коротко, по клику — цитата
export function SiteFacts({ facts }) {
  const [open, setOpen] = React.useState(null)
  return (
    <div className="site-facts" onClick={e => e.stopPropagation()}>
      {facts.map(f => (
        <div key={f.id} className={open === f.id ? 'on' : ''}>
          <button onClick={() => setOpen(open === f.id ? null : f.id)}>
            <Icon name={ICON[f.evidence.topic] || 'check'} size={16} />{f.value.text}
          </button>
          {open === f.id && <SiteQuote quote={f.evidence.quote} url={f.evidence.url} date={f.evidence.fetched_at} />}
        </div>
      ))}
    </div>
  )
}
