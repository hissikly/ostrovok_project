import React from 'react'

// Слой «Осадки»: норма на месяц поездки (GET /api/climate/rain) — плавная синяя заливка поверх карты.
// Сетка 4×7 точек → картинка с билинейной интерполяцией: пятна не накладываются, синее = чаще дожди.
// Шкала относительная внутри месяца (самое сухое место — прозрачно, самое дождливое — синее): иначе разницу побережья и гор не видно
const RAIN_RGB = [47, 111, 224]

export function rainImage({ grid: { lats, lons }, points }) {
  const at = {}
  points.forEach(p => { at[`${p.lat},${p.lon}`] = p.wet_days })
  const v = (i, j) => at[`${lats[i]},${lons[j]}`]
  const ws = points.map(p => p.wet_days), lo = Math.min(...ws), hi = Math.max(...ws)
  const alpha = w => hi > lo ? Math.pow((w - lo) / (hi - lo), 0.7) * 0.65 : 0
  const W = 240, H = 120, c = document.createElement('canvas')
  c.width = W; c.height = H
  const g = c.getContext('2d'), img = g.createImageData(W, H)
  for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
    const fi = (1 - y / (H - 1)) * (lats.length - 1), fj = x / (W - 1) * (lons.length - 1)
    const i = Math.min(Math.floor(fi), lats.length - 2), j = Math.min(Math.floor(fj), lons.length - 2), di = fi - i, dj = fj - j
    const w = v(i, j) * (1 - di) * (1 - dj) + v(i + 1, j) * di * (1 - dj) + v(i, j + 1) * (1 - di) * dj + v(i + 1, j + 1) * di * dj
    const edge = Math.min(1, Math.min(x, W - 1 - x) / (W * 0.12), Math.min(y, H - 1 - y) / (H * 0.15))   // края гаснут: без резкой рамки над морем
    img.data.set([...RAIN_RGB, Math.round(alpha(w) * edge * 255)], (y * W + x) * 4)
  }
  g.putImageData(img, 0, 0)
  const n = lats.at(-1), s = lats[0], west = lons[0], e = lons.at(-1)
  return { url: c.toDataURL(), coordinates: [[west, n], [e, n], [e, s], [west, s]] }
}

const MONTH_IN = ['', 'январе', 'феврале', 'марте', 'апреле', 'мае', 'июне', 'июле', 'августе', 'сентябре', 'октябре', 'ноябре', 'декабре']

// строка легенды карты: переключатель и шкала
export default function RainToggle({ on, setOn, month }) {
  return (
    <div className="rain-toggle">
      <button className={on ? 'on' : ''} onClick={() => setOn(!on)} title="Как часто обычно идут дожди в месяц поездки: норма за 6 лет, Open-Meteo">
        <span className="rain-check">{on ? '✓' : ''}</span>Дожди в {MONTH_IN[month]}
      </button>
      {/* шкала всегда в разметке — выезжает плавно, как у «Линии от моря» */}
      <span className={`rain-scale ${on ? 'on' : ''}`} aria-hidden={!on}>реже <i /> чаще</span>
    </div>
  )
}
