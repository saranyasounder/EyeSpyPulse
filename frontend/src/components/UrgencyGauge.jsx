import { useEffect, useState } from "react";

const SIZE = 160;
const STROKE = 14;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

const TIER_COLORS = {
  critical: "var(--badge-critical)",
  elevated: "var(--badge-elevated)",
  watching: "var(--badge-watching)",
};

function tierFor(score) {
  if (score == null) return "watching";
  if (score >= 0.66) return "critical";
  if (score >= 0.4) return "elevated";
  return "watching";
}

export default function UrgencyGauge({ score, label }) {
  const [filled, setFilled] = useState(false);

  useEffect(() => {
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) {
      setFilled(true);
      return;
    }
    const id = requestAnimationFrame(() => setFilled(true));
    return () => cancelAnimationFrame(id);
  }, []);

  const clamped = Math.max(0, Math.min(1, score ?? 0));
  const tier = tierFor(score);
  const offset = CIRCUMFERENCE * (1 - (filled ? clamped : 0));

  return (
    <div
      className="gauge"
      role="img"
      aria-label={score != null ? `${label}: urgency ${clamped.toFixed(2)} out of 1.00` : "No ranked topic yet"}
    >
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} aria-hidden="true">
        <circle cx={SIZE / 2} cy={SIZE / 2} r={RADIUS} fill="none" stroke="var(--bg-dot)" strokeWidth={STROKE} />
        <circle
          cx={SIZE / 2}
          cy={SIZE / 2}
          r={RADIUS}
          fill="none"
          stroke={TIER_COLORS[tier]}
          strokeWidth={STROKE}
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${SIZE / 2} ${SIZE / 2})`}
          className="gauge__ring"
        />
      </svg>
      <div className="gauge__value" aria-hidden="true">
        <strong>{score != null ? clamped.toFixed(2) : "—"}</strong>
        <span>urgency</span>
      </div>
    </div>
  );
}