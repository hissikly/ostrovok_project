import React, { useEffect, useState } from 'react'
import { api, post } from '@app/api.js'
import Icon from '@app/icons.jsx'
import './characteristics.css'

// «Научить О!кно»: описать новую характеристику текстом → агент собирает план поиска → посчитать для всех отелей.
// Экран #admin. LLM (если есть ключ) только собирает план; ответы дают инструменты: карта, отметки отеля, его ответы.
const EXAMPLES = ['Есть ли рядом велодорожки', 'Нет ли рядом стройки', 'Есть ли в номере сейф', 'Можно ли курить в номере',
  'Теннисный корт в 10 минутах']
const TOOL_ICON = { poi_nearby: 'pin', hotel_osm: 'building', hotel_answers: 'mail', web_text: 'window',
  ask_hotelier: 'users', viewshed: 'waves', walk_route: 'beach', noise_model: 'mute', climate: 'sunset' }
const plural = (n, one, few, many) => {
  const m10 = n % 10, m100 = n % 100
  return m10 === 1 && m100 !== 11 ? one : m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20) ? few : many
}

function Progress({ st }) {
  const pct = st.total ? Math.round(100 * st.done / st.total) : 0
  return (
    <div className="ch-progress">
      <div className="meter"><i style={{ width: `${pct}%` }} /></div>
      {st.state === 'running'
        ? <div className="muted">Проверяем отели: {st.done} из {st.total}</div>
        : st.state === 'error' ? <div className="ch-warn">Не получилось посчитать: {st.error}</div>
          : <div className="ch-done">
              <div><b>{st.answered}</b>{plural(st.answered, 'отель', 'отеля', 'отелей')} — ответ нашли</div>
              {st.asked > 0 && <div><b>{st.asked}</b>{plural(st.asked, 'отелю', 'отелям', 'отелям')} задали вопрос</div>}
              {st.unknown > 0 && <div><b>{st.unknown}</b>пока не знаем</div>}
            </div>}
    </div>
  )
}

function Draft({ d, onSaved, onReset }) {
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState(null)
  const s = d.spec
  const save = async () => {
    setBusy(true); setErr(null)
    try { onSaved(await post('/api/characteristics', { spec: s, run: true })) } catch (e) { setErr(String(e)); setBusy(false) }
  }
  const kind = s.kind === 'near' ? (s.prefer === 'far' ? 'Место рядом: хорошо, если его нет' : 'Место рядом с отелем')
    : 'Да или нет — об отеле или номере'
  return (
    <div className="block">
      <div className="ch-cap">Как поняли</div>
      <div className="ch-head">
        <div className="ch-ic"><Icon name={s.icon} /></div>
        <div>
          <h2 style={{ margin: 0 }}>{s.title}</h2>
          <div className="muted">{kind}</div>
        </div>
      </div>
      <div className="ch-cap" style={{ marginTop: 18 }}>Где искать ответ</div>
      <ol className="ch-plan">
        {d.plan.map((p, i) => <li key={i}><Icon name={TOOL_ICON[s.plan[i]?.tool] || 'pin'} size={18} /><span>{p}</span></li>)}
      </ol>
      {d.warnings.map(w => <div key={w} className="ch-warn">{w}</div>)}
      {d.errors.map(w => <div key={w} className="ch-warn err">{w}</div>)}
      {s.note && <div className="ch-warn">{s.note}</div>}
      <div className="ch-by">{d.by === 'llm' ? 'План собрала языковая модель и проверили правила' : 'План собран правилами, без языковой модели'}</div>
      {err && <div className="ch-warn err">{err}</div>}
      <div className="ch-actions">
        <button className="ext-btn pri" disabled={busy || d.errors.length > 0} onClick={save}>Посчитать для всех отелей</button>
        <button className="ext-btn sec" onClick={onReset}>Описать иначе</button>
      </div>
    </div>
  )
}

function Added({ items, onRemove }) {
  const mine = items.filter(c => !['builtin', 'nearby'].includes(c.origin))
  const known = items.length - mine.length
  return (
    <div className="block">
      <h2>Уже умеем</h2>
      {mine.map(c => (
        <div key={c.id} className="ch-item">
          <div className="ch-ic sm"><Icon name={c.icon || 'pin'} size={18} /></div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <b>{c.title}</b>
            <div className="muted">«{c.text}»{c.status?.state === 'done' && `, ответ у ${c.status.answered} из ${c.status.total}`}</div>
          </div>
          <button className="ch-x" title="Убрать" aria-label="Убрать" onClick={() => onRemove(c.id)}><Icon name="x" size={16} /></button>
        </div>
      ))}
      <div className="muted" style={{ marginTop: mine.length ? 12 : 0 }}>
        {mine.length ? 'И ещё ' : ''}{known} {plural(known, 'характеристика', 'характеристики', 'характеристик')} из коробки:
        вид на море, закат, путь до пляжа, тишина ночью, Wi-Fi и всё «что рядом».</div>
    </div>
  )
}

function Tools({ tools }) {
  return (
    <div className="block">
      <h2>Где агент ищет</h2>
      <p className="lead">Агент сам выбирает источники по порядку надёжности. Факты дают только они, модель их не придумывает.</p>
      {tools.map(t => (
        <div key={t.id} className={`ch-tool ${t.available ? '' : 'off'}`}>
          <Icon name={TOOL_ICON[t.id] || 'pin'} size={18} />
          <div><b>{t.title}</b>{!t.available && <span className="ch-soon">скоро</span>}<div className="muted">{t.about}</div></div>
        </div>
      ))}
    </div>
  )
}

export default function AddCharacteristic({ onExit }) {
  const [text, setText] = useState('')
  const [d, setD] = useState(null)
  const [busy, setBusy] = useState(false)
  const [job, setJob] = useState(null)        // {spec, status}
  const [items, setItems] = useState([])
  const [tools, setTools] = useState([])
  const reload = () => api('/api/characteristics').then(setItems).catch(() => {})
  useEffect(() => { reload(); api('/api/characteristics/tools').then(setTools).catch(() => {}) }, [])
  // прогресс прогона по всем отелям
  useEffect(() => {
    if (!job || job.status?.state !== 'running') return
    const t = setTimeout(() => api(`/api/characteristics/${job.spec.id}/status`)
      .then(st => { setJob(j => ({ ...j, status: st })); if (st.state !== 'running') reload() }), 500)
    return () => clearTimeout(t)
  }, [job])

  const parse = async (e, t = text) => {
    e?.preventDefault()
    if (!t.trim()) return
    setText(t); setBusy(true); setJob(null)
    try { setD(await post('/api/characteristics/from-text', { text: t })) } finally { setBusy(false) }
  }
  const remove = async id => { await fetch(`/api/characteristics/${id}`, { method: 'DELETE' }); reload() }

  return (
    <div className="ext">
      <header className="hdr">
        <div className="logo">Островок!</div>
        <span className="chip lime">О!кно</span>
        <span className="ext-logo-sub">Новые вопросы об отелях</span>
        <button className="for-hotels" style={{ marginLeft: 'auto' }} onClick={onExit}>← К подбору отелей</button>
      </header>
      <div className="ch-main">
        <div>
          <div className="block ch-hero">
            <h1>Научить О!кно новому вопросу</h1>
            <p className="lead">Опишите своими словами, что гостям важно знать об отеле. Агент поймёт, где искать ответ,
              проверит все отели Сочи и добавит новый фильтр в подбор.</p>
            <form className="describe ch-input" onSubmit={parse}>
              <Icon name="sparkle" />
              <input placeholder="Например: есть ли рядом велодорожки" value={text} onChange={e => setText(e.target.value)} />
              {text.trim() && <button className="go" disabled={busy}>{busy ? 'Разбираем…' : 'Разобрать'}</button>}
            </form>
            <div className="pills ch-examples">{EXAMPLES.map(x => <button key={x} onClick={() => parse(null, x)}>{x}</button>)}</div>
          </div>
          {d?.exists && <div className="block">
            <h2 style={{ marginTop: 0 }}>Это мы уже знаем</h2>
            <p className="lead">Фильтр «{d.exists.title}» уже есть в подборе и в карточках отелей — найдите его в «Ещё фильтры».</p>
          </div>}
          {d?.spec && !job && <Draft d={d} onReset={() => { setD(null); setText('') }}
            onSaved={r => { setJob(r); reload() }} />}
          {job && <div className="block">
            <div className="ch-cap">{job.spec.title}</div>
            <h2 style={{ marginTop: 4 }}>{job.status?.state === 'done' ? 'Готово' : 'Считаем для всех отелей'}</h2>
            {job.status && <Progress st={job.status} />}
            {job.status?.state === 'done' && <p className="lead" style={{ marginTop: 12 }}>
              Новый фильтр «{job.spec.title}» уже в подборе («Ещё фильтры» и «✨ опиши»), ответ — в карточке каждого отеля
              вместе с тем, как агент его искал.{job.status.asked > 0 && ' Вопросы отелям — в разделе «Для отелей».'}</p>}
            {job.status?.state === 'done' && <div className="ch-actions">
              <button className="ext-btn pri" onClick={() => { location.hash = 'w201474333' }}>Посмотреть в карточке отеля</button>
              <button className="ext-btn sec" onClick={() => { setJob(null); setD(null); setText('') }}>Добавить ещё</button>
            </div>}
          </div>}
          <Added items={items} onRemove={remove} />
        </div>
        <aside className="ch-aside"><Tools tools={tools} /></aside>
      </div>
    </div>
  )
}
