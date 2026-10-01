import { useEffect, useState } from "react";
import { labelFor, urgencyBand } from "../constants";

export default function UrgencyBarChart({ topics }) {
  const [filled, setFilled] = useState(false);
  const ranked = topics.filter((t) => t.ranked);

  useEffect(() => {
    const prefersReduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) {
      setFilled(true);
      return;
    }
    const id = requestAnimationFrame(() => setFilled(true));
    return () => cancelAnimationFrame(id);
  }, []);

  if (ranked.length === 0) return null;

  return (
    <section className="bar-chart" aria-labelledby="bar-chart-heading">
      <h2 id="bar-chart-heading" className="section-heading">
        Urgency by Topic
      </h2>
      <ul className="bar-chart__list">
        {ranked.map((topic) => {
          const band = urgencyBand(topic.urgency_score);
          const pct = Math.round(Math.max(0, Math.min(1, topic.urgency_score ?? 0)) * 100);
          return (
            <li key={topic.focus_area} className="bar-chart__row">
              <span className="bar-chart__label">{labelFor(topic)}</span>
              <div className="bar-chart__track" aria-hidden="true">
                <div
                  className={`bar-chart__fill bar-chart__fill--${band?.tier ?? "watching"}`}
                  style={{ width: filled ? `${pct}%` : "0%" }}
                />
              </div>
              <span className="bar-chart__score">{topic.urgency_score.toFixed(2)}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}