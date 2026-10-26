import React, { useState } from 'react'
import Icon from '@app/icons.jsx'
import { ConflictNote, ROW_TOPIC, useConflicts } from '@features/conflicts/frontend/ConflictNote.jsx'
import { SiteFacts, SITE_ROW } from '@features/web_sources/frontend/SiteQuote.jsx'
import './facts.css'

const SIDE = { N: 'север', E: 'восток', S: 'юг', W: 'запад' }
const ORDER = ['W', 'S', 'N', 'E']
// Откуда мы это знаем — одной фразой, без дат и оговорок
export const HOW = {
  'computed:dem': 'Посчитали по карте рельефа.',
  'computed:horizon': 'Посчитали по рельефу и высоте соседних домов.',
  'computed:horizon+sun': 'Посчитали по высоте домов вокруг и движению солнца.',
  'computed:osm-poi': 'Нашли на открытой карте ближайшее место каждого типа и посчитали путь пешком по прямой: настоящий путь может быть длиннее.',
  'computed:osm-poi+walk': 'Нашли на открытой карте ближайшее место каждого типа и посчитали путь пешком по улицам, с учётом подъёмов.',
  'computed:walk-graph': 'Проложили путь пешком по улицам и тропам открытой карты, подъём — по карте высот.',
  'computed:noise-model': 'Оценили по карте: какие дороги, железная дорога, бары и аэропорт рядом и с какой стороны здания они.',
  'computed:osm-beach': 'Измерили по открытой карте до ближайшего пляжа, по прямой: настоящий путь может быть длиннее.',
  hotelier: 'Так ответил отель.', osm: 'Взяли с открытой карты.',
}

// где фраза об уверенности лишняя: пояснение и так говорит, что это оценка по карте
const NO_SURE = ['computed:noise-model']

// Уверенность — словами, без процентов (wiki/design-system.md)
export function sureWord(c) {
  return c >= 0.8 ? ['точно', 'hi'] : c >= 0.6 ? ['по расчёту', 'mid'] : ['примерно', 'lo']
}

const sideOf = f => f.scope.split(':')[1]
// «Магнит», но не ««Южная»» — если кавычки уже есть в названии из OSM
export const quote = name => !name ? '' : /[«"„“]/.test(name) ? name : `«${name}»`
// что показываем в «Что рядом» сразу; остальное — «ещё N» или фильтром по группам
const NEAR_MAIN = ['grocery', 'pharmacy', 'cafe', 'park', 'playground', 'bus', 'atm']
const GROUPS = [['Магазины', 'cart'], ['Еда', 'cup'], ['Отдых', 'tree'], ['Дети', 'child'], ['Здоровье', 'cross'],
  ['Ночью', 'moon'], ['Транспорт', 'bus'], ['Питомцы', 'paw'], ['Прочее', 'star']]
const dist = m => (m < 1000 ? `${m} м` : `${(m / 1000).toFixed(1).replace('.', ',')} км`)

// «Что рядом»: фильтр-иконки по группам и строки одинаковой высоты (иконка типа, что и как называется, минуты)
// Свернуть / развернуть длинную строку; выбор помним в браузере гостя
const FOLD = 'fold:near'
const readFold = k => { try { return localStorage.getItem(k) === '1' } catch { return false } }
const saveFold = (k, v) => { try { localStorage.setItem(k, v ? '1' : '0') } catch { /* без хранилища — просто не помним */ } }
export function FoldButton({ folded, onClick }) {
  return (
    <button className={`fold ${folded ? 'folded' : ''}`} onClick={e => { e.stopPropagation(); onClick() }}
      aria-expanded={!folded} aria-label={folded ? 'Развернуть' : 'Свернуть'} title={folded ? 'Развернуть' : 'Свернуть'}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d="M6 15l6-6 6 6" /></svg>
    </button>
  )
}

function NearList({ facts, meta, onPlace, activePlace }) {
  const [groups, setGroups] = useState([])
  const [all, setAll] = useState(false)
  const spec = f => f.characteristic.slice(5)
  const groupOf = f => meta?.[spec(f)]?.group
  const present = GROUPS.filter(([g]) => facts.some(f => groupOf(f) === g))
  const shown = groups.length ? facts.filter(f => groups.includes(groupOf(f)))
    : all ? facts : facts.filter(f => NEAR_MAIN.includes(spec(f)))
  const rest = groups.length || all ? 0 : facts.length - shown.length
  const toggle = g => setGroups(groups.includes(g) ? groups.filter(x => x !== g) : [...groups, g])
  return (
    <div onClick={e => e.stopPropagation()}>
      {present.length > 1 && <div className="near-filter">
        {present.map(([g, icon]) => (
          <button key={g} title={g} aria-label={g} aria-pressed={groups.includes(g)}
            className={groups.includes(g) ? 'on' : ''} onClick={() => toggle(g)}>
            <Icon name={icon} size={16} />{groups.includes(g) && <span>{g}</span>}
          </button>
        ))}
      </div>}
      <div className="near">{shown.map(f => {
        const s = spec(f), v = f.value
        return (
          // клик — все такие места рядом на карте и путь до ближайшего
          <div key={s} className={s === activePlace ? 'on' : ''} onClick={() => onPlace?.(s === activePlace ? null : s)}>
            <Icon name={meta?.[s]?.icon || 'pin'} size={18} />
            <span>{v.kind}<i>{quote(v.name) || `в ${dist(v.meters)} от отеля`}</i></span>
            <b>{v.walk_min} мин</b>
          </div>
        )
      })}</div>
      {rest > 0 && <div className="more-link" onClick={() => setAll(true)}>Ещё {rest}</div>}
    </div>
  )
}
const M = ['', 'янв', 'фев', 'мар', 'апр', 'май', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек']
const M_IN = ['', 'январе', 'феврале', 'марте', 'апреле', 'мае', 'июне', 'июле', 'августе', 'сентябре', 'октябре', 'ноябре', 'декабре']

// [4,5,6,7,8,9,10] → «апр–окт», [10] → «в октябре», [4,5,9] → «апр, май, сен»
function monthRange(ms) {
  if (ms.length === 1) return `в ${M_IN[ms[0]]}`
  const solid = ms.every((m, i) => i === 0 || m === ms[i - 1] + 1)
  return solid ? `${M[ms[0]]}–${M[ms[ms.length - 1]]}` : ms.map(m => M[m]).join(', ')
}

// Факты по сторонам здания сводим в одну понятную строку
function group(facts) {
  const rows = []
  const sea = facts.filter(f => f.characteristic === 'sea_view')
  if (sea.length) {
    const by = Object.fromEntries(sea.map(f => [sideOf(f), f]))
    const lines = ORDER.filter(s => by[s]).map(s => {
      const { from_floor: fl, glimpse_from: gl } = by[s].value
      if (fl) return [SIDE[s], fl === 1 ? 'с любого этажа' : `с ${fl}-го этажа`]
      if (gl) return [SIDE[s], `краешком с ${gl}-го этажа`]
      return [SIDE[s], 'не видно']
    })
    const any = sea.some(f => f.value.from_floor)
    rows.push({ key: 'sea', icon: 'waves', title: any ? 'Есть номера с видом на море' : 'Вида на море нет',
      lines, facts: sea })
  }
  const sun = facts.filter(f => f.characteristic === 'sunset_view')
  if (sun.length) {
    const by = Object.fromEntries(sun.map(f => [sideOf(f), f]))
    const lines = ORDER.filter(s => by[s]).map(s => [SIDE[s], monthRange(by[s].value.months)])
    rows.push({ key: 'sun', icon: 'sunset', title: 'Закат над морем из окна', lines, facts: sun })
  }
  // тишина ночью: по сторонам здания или у отеля целиком
  const noise = facts.filter(f => f.characteristic === 'noise')
  if (noise.length) {
    const LEVEL = { quiet: 'тихо', calm: 'спокойно', noisy: 'шумно', very_noisy: 'очень шумно' }
    const why = v => v.source && ['noisy', 'very_noisy'].includes(v.level) ? `, ${v.source.kind_ru}` : ''
    const best = noise.reduce((a, b) => (a.value.night_db <= b.value.night_db ? a : b))
    const sides = noise.filter(f => f.scope.startsWith('facade:'))
    const anyQuiet = noise.some(f => ['quiet', 'calm'].includes(f.value.level))
    if (sides.length) {
      const by = Object.fromEntries(sides.map(f => [sideOf(f), f]))
      rows.push({ key: 'noise', icon: 'mute', title: anyQuiet ? 'Ночью есть тихая сторона' : 'Ночью шумно со всех сторон',
        lines: ORDER.filter(s => by[s]).map(s => [SIDE[s], LEVEL[by[s].value.level] + why(by[s].value)]), facts: sides })
    } else {
      const v = best.value
      rows.push({ key: 'noise', icon: 'mute', title: `Ночью у отеля ${LEVEL[v.level]}`,
        text: v.source && ['noisy', 'very_noisy'].includes(v.level) ? `Рядом ${v.source.kind_ru}, ${v.source.meters} м` : '', facts: [best] })
    }
  }
  const route = facts.find(f => f.characteristic === 'beach_route')
  const beach = !route && facts.find(f => f.characteristic === 'beach_distance')
  if (route) {
    const v = route.value
    const notes = [v.steps && 'лестницы', v.underpass && 'подземный переход', v.bridge && 'мост или надземный переход',
      v.rail && 'переход через ж/д', v.major_m >= 100 && 'вдоль большой дороги'].filter(Boolean)
    rows.push({ key: 'beach', icon: 'beach', beach: true, title: `До пляжа ${v.minutes} мин пешком`,
      text: ((v.climb_back_m ?? v.down_m) > 10 ? `Обратно ${v.back_minutes} мин в гору, подъём ${v.climb_back_m ?? v.down_m} м` : `Обратно ${v.back_minutes} мин, почти ровно`)
        + (notes.length ? `. По пути: ${notes.join(', ')}` : ''), facts: [route] })
  }
  if (beach) {
    const m = beach.value.meters
    rows.push({ key: 'beach', icon: 'beach', beach: true, title: `До пляжа ${m < 1000 ? `${m} м` : `${(m / 1000).toFixed(1).replace('.', ',')} км`}`,
      text: `Около ${beach.value.walk_min} мин пешком`, facts: [beach] })
  }
  // «что рядом»: одна строка-таблица, ближайшее из главного; остальное — по клику
  const near = facts.filter(f => f.characteristic.startsWith('near:') && f.value.meters != null)
    .sort((a, b) => a.value.walk_min - b.value.walk_min)
  if (near.length) rows.push({ key: 'near', icon: 'pin', title: 'Что рядом пешком', near: true, facts: near })
  // с сайта отеля — одной строкой с цитатами; ответы на частые вопросы — в «Частых вопросах»
  const site = facts.filter(f => f.characteristic.startsWith('web:') && SITE_ROW.includes(f.evidence?.topic))
  if (site.length) rows.push({ key: 'site', icon: 'building', title: 'На сайте отеля пишут', site: true, facts: site })
  for (const f of facts.filter(f => !['sea_view', 'sunset_view', 'beach_distance', 'beach_route', 'noise'].includes(f.characteristic)
    && !f.characteristic.startsWith('near:') && !f.characteristic.startsWith('web:'))) {
    rows.push({ key: f.id, icon: 'window', title: f.value?.text || f.characteristic, text: '', facts: [f] })
  }
  return rows
}

function Row({ r, onPlace, activePlace, onBeach, beachOn, nearMeta, conflict }) {
  const [open, setOpen] = useState(false)
  const [folded, setFolded] = useState(() => r.near && readFold(FOLD))
  const fold = () => { saveFold(FOLD, !folded); setFolded(!folded) }
  // свёрнутое «что рядом» — одной строкой: три ближайших места
  const nearBrief = r.near && r.facts.slice(0, 3).map(f => `${f.value.kind.toLowerCase()} ${f.value.walk_min} мин`).join(', ')
  const lines = r.lines
  const c = Math.min(...r.facts.map(f => f.confidence))
  const f0 = r.facts[0]
  // уверенность — не плашкой (занимает место), а фразой в «как узнали» по клику
  const sure = { hi: 'Данные надёжные.', mid: 'Это расчёт: на месте может немного отличаться.', lo: 'Это примерная оценка.' }[sureWord(c)[1]]
  return (
    <div className="fact" onClick={() => setOpen(!open)}>
      <div className="ic"><Icon name={r.icon} /></div>
      <div style={{ flex: 1 }}>
        <div className="t">{r.title}{r.near && <FoldButton folded={folded} onClick={fold} />}</div>
        {r.text && <div className="s">{r.text}</div>}
        {r.near && folded && <div className="s">{nearBrief[0].toUpperCase() + nearBrief.slice(1)}</div>}
        {r.site && <SiteFacts facts={r.facts} />}
        {r.near && !folded && <NearList facts={r.facts} meta={nearMeta} onPlace={onPlace} activePlace={activePlace} />}
        {!r.near && lines && <div className="sides">{lines.map(([side, v]) =>
          <div key={side}><span>{side[0].toUpperCase() + side.slice(1)}</span><b className={v === 'не видно' || v.startsWith('шумно') || v.startsWith('очень') ? 'no' : ''}>{v}</b></div>)}</div>}
        {r.beach && onBeach && <div className={`more-link ${beachOn ? 'on' : ''}`}
          onClick={e => { e.stopPropagation(); onBeach() }}>Показать путь на карте</div>}
        {open && !r.site && !(r.near && folded) && <div className="how">{HOW[f0.source] || f0.source}{NO_SURE.includes(f0.source) ? '' : ` ${sure}`}</div>}
        <ConflictNote c={conflict} compact />
      </div>
    </div>
  )
}

// children — строки, которые дописывают другие фичи (ответы агента «Что ещё узнали»), внутри того же блока
export default function FactList({ facts, onPlace, activePlace, onBeach, beachOn, nearMeta, children }) {
  const rows = group(facts)
  const conflicts = useConflicts(facts[0]?.hotel_id)
  if (!rows.length && !children) return null
  return (
    <div className="block">
      <h2>Что важно знать</h2>
      <p className="lead">Этого нет в описании отеля, мы проверили сами.</p>
      {rows.map(r => <Row key={r.key} r={r} onPlace={onPlace} activePlace={activePlace} onBeach={onBeach} beachOn={beachOn}
        nearMeta={nearMeta} conflict={conflicts[ROW_TOPIC[r.key]]} />)}
      {children}
    </div>
  )
}
