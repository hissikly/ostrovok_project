import React from 'react'

// Пожелание к номеру картинкой: дом сбоку, окна смотрят на выбранную сторону (всегда влево),
// подсвечены этажи «N и выше», ваш этаж — точка с конусом взгляда, как в «О!кне» на карте.
// Море и закат — только если они есть в пожелании; справа улица с шумом, если просили тихую сторону.
const SIDE = { N: 'север', E: 'восток', S: 'юг', W: 'запад' }
// где шумнее — из причины пункта «Тихая сторона»: «На северной стороне ночью громче…»
const LOUD = { северной: 'на севере', южной: 'на юге', восточной: 'на востоке', западной: 'на западе' }
const BRAND = '#0E41D2'
const W = 340, H = 168, GROUND = 140, TOP = 18
const BX = 150, BW = 72   // дом

export default function WishPicture({ facade, floor, levels, items }) {
  const by = Object.fromEntries(items.map(it => [it.id, it]))
  const side = by.side, fl = by.floor, quiet = by.quiet
  const sea = side && /мор/i.test(side.reason)
  const sunset = side && /закат/i.test(side.reason)
  const loud = quiet && LOUD[(quiet.reason.match(/^На (\S+) стороне/) || [])[1]]
  const n = Math.max(levels || 0, floor || 0, fl?.min_floor || 0, 3)
  const fh = (GROUND - TOP) / n
  const yOf = i => GROUND - i * fh            // верх этажа i (снизу 1)
  const want = i => fl ? i >= fl.min_floor : i === floor
  const my = floor ? yOf(floor) + fh / 2 : null
  const cols = BW > 60 ? 5 : 4

  return (
    <svg className="tr-pic" viewBox={`0 0 ${W} ${H}`} role="img"
      aria-label={`Окна на ${SIDE[facade] || 'выбранную сторону'}${floor ? `, ${floor} этаж` : ''}`}>
      <defs>
        <linearGradient id="trsky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={sunset ? '#FFE9CF' : '#E3EBFD'} />
          <stop offset="1" stopColor="#FFFFFF" />
        </linearGradient>
        <linearGradient id="trcone" x1="1" y1="0" x2="0" y2="0">
          <stop offset="0" stopColor={BRAND} stopOpacity=".28" />
          <stop offset="1" stopColor={BRAND} stopOpacity="0" />
        </linearGradient>
      </defs>
      <rect width={W} height={GROUND} rx="14" fill="url(#trsky)" />

      {/* закат и море на стороне окон */}
      {sunset && <g>
        <circle cx="46" cy={GROUND - 20} r="15" fill="#FFB547" />
        {[-50, -25, 0, 25, 50].map(a => {
          const r = a * Math.PI / 180
          return <line key={a} x1={46 + Math.sin(r) * 21} y1={GROUND - 20 - Math.cos(r) * 21}
            x2={46 + Math.sin(r) * 27} y2={GROUND - 20 - Math.cos(r) * 27} stroke="#FFB547" strokeWidth="2.4" strokeLinecap="round" />
        })}
      </g>}
      {sea
        ? <g>
            <path d={`M0 ${GROUND - 14} H128 L136 ${GROUND} H0 Z`} fill="#8FB0FF" />
            {[0, 1].map(k => <path key={k} d={`M${10 + k * 22} ${GROUND - 8 + k * 4} q8 -5 16 0 t16 0 t16 0`} fill="none"
              stroke="#fff" strokeWidth="1.8" strokeLinecap="round" opacity=".85" />)}
          </g>
        : <rect x="0" y={GROUND - 4} width={BX} height="4" fill="#DDE3EA" />}

      {/* взгляд из вашего окна */}
      {my != null && <path d={`M${BX} ${my} L18 ${my - 34} Q8 ${my + 4} 18 ${Math.min(my + 40, GROUND)} Z`} fill="url(#trcone)" />}

      {/* дом: этажи, подходящие — синим */}
      <rect x={BX} y={TOP} width={BW} height={GROUND - TOP} rx="3" fill="#EEF0F3" />
      {Array.from({ length: n }, (_, k) => k + 1).map(i => (
        <g key={i}>
          {want(i) && <rect x={BX} y={yOf(i)} width={BW} height={fh} fill="#D6E2FF" />}
          {Array.from({ length: cols }, (_, c) => (
            <rect key={c} x={BX + 6 + c * ((BW - 12) / cols) + 1} y={yOf(i) + fh * .25} width={(BW - 12) / cols - 4}
              height={Math.max(fh * .5, 1.5)} rx=".8" fill={want(i) ? '#8FAEFF' : '#C9CDD4'} />
          ))}
        </g>
      ))}
      {my != null && <circle cx={BX} cy={my} r="5.5" fill="#fff" stroke={BRAND} strokeWidth="3" />}
      {my != null && <text x={BX - 10} y={Math.max(my - 9, TOP + 8)} textAnchor="end" className="tr-pic-lbl strong">ваш {floor}-й</text>}

      {/* скобка этажей справа от дома */}
      {fl && <g>
        <path d={`M${BX + BW + 5} ${yOf(n) + 1} h4 V${yOf(fl.min_floor - 1) - 1} h-4`} fill="none" stroke={BRAND} strokeWidth="1.6" />
        <text x={BX + BW + 14} y={(yOf(n) + yOf(fl.min_floor - 1)) / 2 + 4} className="tr-pic-lbl strong">
          {fl.min_floor === n ? 'верхний' : `${fl.min_floor}–${n} этаж`}</text>
      </g>}

      {/* шумная сторона за домом */}
      <rect x={BX + BW} y={GROUND - 4} width={W - BX - BW} height="4" fill="#DDE3EA" />
      {quiet && <g stroke="#B5BAC2" strokeWidth="1.8" fill="none" strokeLinecap="round">
        <rect x="282" y={GROUND - 13} width="22" height="9" rx="3" fill="#C9CDD4" stroke="none" />
        {[8, 15, 22].map(r => <path key={r} d={`M${270 - r * .2} ${GROUND - 9 - r} a${r} ${r} 0 0 0 0 ${r * 1.4}`}
          transform={`translate(${-r * .4} 0)`} />)}
      </g>}

      <text x="64" y={H - 8} textAnchor="middle" className="tr-pic-lbl">{SIDE[facade] ? `окна на ${SIDE[facade]}` : ''}{sea ? ', море' : ''}</text>
      <text x={BX + BW / 2} y={H - 8} textAnchor="middle" className="tr-pic-lbl">{levels ? `${levels} этажей` : ''}</text>
      {quiet && <text x={W - 8} y={H - 8} textAnchor="end" className="tr-pic-lbl">{loud ? `${loud} шумнее` : 'шумнее'}</text>}
    </svg>
  )
}
