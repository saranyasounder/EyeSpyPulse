import UrgencyGauge from "./UrgencyGauge";
import { labelFor, trendDisplay } from "../constants";

function totalPosts(topics) {
  return topics.reduce((sum, t) => sum + (t.post_count || 0), 0);
}

export default function FrictionSnapshot({ topics, asOf }) {
  const ranked = topics.filter((t) => t.ranked);
  const lead = ranked[0];
  const label = lead ? labelFor(lead) : null;
  const trend = lead ? trendDisplay(lead.trend) : null;
  const updated = asOf
    ? new Date(asOf).toLocaleDateString(undefined, { month: "short", day: "numeric" })
    : null;

  return (
    <section className="snapshot" aria-labelledby="snapshot-heading">
      <UrgencyGauge score={lead?.urgency_score} label={label ?? "no ranked topic"} />

      <div className="snapshot__text">
        <h2 id="snapshot-heading">This Week's Key Finding</h2>
        {lead ? (
          <p className="snapshot__lead">
            <strong>{label}</strong> is the most urgent topic this week —{" "}
            <span aria-hidden="true">{trend.icon} </span>
            {trend.text.toLowerCase()}, based on {lead.post_count} posts.
          </p>
        ) : (
          <p className="snapshot__lead">Not enough data yet to identify a top topic.</p>
        )}
        <p className="snapshot__meta">
          {topics.length} topics tracked · {totalPosts(topics)} posts this week
          {updated && ` · updated ${updated}`}
        </p>
      </div>
    </section>
  );
}