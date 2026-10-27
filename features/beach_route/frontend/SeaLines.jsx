import React from 'react'

// Линия от моря (1–4, считает backend/lines.py) — песочным ореолом под точкой отеля (песок = пляж; на голубом море и зелёных парках не теряется):
// чем ближе к морю, тем ярче. Цвет самих точек не трогаем — он занят подбором и «О!кном»
export const SEA_COLOR = '#F2A93B'
export const SEA_OPACITY = ['match', ['get', 'line'], 1, 0.7, 2, 0.42, 3, 0.2, 0]
export const SEA_RADIUS = ['interpolate', ['linear'], ['zoom'], 11, 10, 14, 18, 17, 28]
const STEPS = [[1, '1-я'], [2, '2-я'], [3, '3-я']]

// строка легенды карты: шкала линий и переключатель
export default function SeaLines({ on, setOn }) {
  return (
    <div className="sea-lines">
      <button className={on ? 'on' : ''} onClick={() => setOn(!on)} title="Как далеко отель от моря: по пешему пути до пляжа">
        <span className="sea-lines-check">{on ? '✓' : ''}</span>Линия от моря
      </button>
      {on && STEPS.map(([n, t]) => (
        <span key={n} className="sea-lines-step"><i style={{ background: SEA_COLOR, opacity: SEA_OPACITY[2 * n + 1] }} />{t}</span>
      ))}
    </div>
  )
}
