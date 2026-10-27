import React from 'react'

// Линия от моря (1–4, считает backend/lines.py) — бирюзовым ореолом под точкой отеля:
// чем ближе к морю, тем ярче. Цвет самих точек не трогаем — он занят подбором и «О!кном»
export const SEA_COLOR = '#12BFB0'
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
      {/* шкала всегда в разметке — выезжает и прячется плавно, легенда растягивается вместе с ней */}
      <span className={`sea-lines-steps ${on ? 'on' : ''}`} aria-hidden={!on}>
        {STEPS.map(([n, t]) => (
          <span key={n} className="sea-lines-step"><i style={{ background: SEA_COLOR, opacity: SEA_OPACITY[2 * n + 1] }} />{t}</span>
        ))}
      </span>
    </div>
  )
}
