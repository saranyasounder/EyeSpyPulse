import { labelFor, urgencyBand, trendDisplay } from "../constants";

function TopicRow({ topic }) {
  const label = labelFor(topic);
  const band = urgencyBand(topic.urgency_score);
  const trend = trendDisplay(topic.trend);

  return (
    <tr className={!topic.ranked ? "row--limited" : undefined} data-tier={band?.tier}>
      <th scope="row" className="col-rank">
        {topic.ranked ? `#${topic.rank}` : "—"}
      </th>
      <td className="col-topic">
        {label}
        <span className="sr-only"> — {topic.summary}</span>
      </td>
      <td className="col-urgency">
        {topic.urgency_score != null ? topic.urgency_score.toFixed(2) : "—"}
      </td>
      <td className="col-level">
        {band && <span className={`badge badge--${band.tier}`}>{band.label}</span>}
      </td>
      <td className="col-trend">
        <span aria-hidden="true">{trend.icon} </span>
        {trend.text}
      </td>
      <td className="col-posts">{topic.post_count}</td>
      <td className="col-friction">
        {topic.avg_friction != null ? topic.avg_friction.toFixed(2) : "—"}
      </td>
    </tr>
  );
}

function TopicTable({ topics, caption }) {
  return (
    <div className="table-scroll">
      <table className="topics-table">
        <caption>{caption}</caption>
        <thead>
          <tr>
            <th scope="col">Rank</th>
            <th scope="col">Topic</th>
            <th scope="col">Urgency</th>
            <th scope="col">Level</th>
            <th scope="col">Trend</th>
            <th scope="col">Posts (7d)</th>
            <th scope="col">Avg. Friction</th>
          </tr>
        </thead>
        <tbody>
          {topics.map((t) => (
            <TopicRow key={t.focus_area} topic={t} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function TopicsTable({ topics }) {
  const ranked = topics.filter((t) => t.ranked);
  const limited = topics.filter((t) => !t.ranked);

  return (
    <div className="topics-tables">
      <section aria-labelledby="ranked-heading">
        <h2 id="ranked-heading" className="section-heading">
          All Tracked Topics
        </h2>
        <TopicTable topics={ranked} caption="Topics ranked by urgency score, most urgent first" />
      </section>

      {limited.length > 0 && (
        <section aria-labelledby="limited-heading" className="limited-section">
          <h2 id="limited-heading" className="section-heading">
            Not enough data to rank yet
          </h2>
          <p className="section-note">
            Fewer than 3 posts this week — not enough for a fair urgency comparison.
          </p>
          <TopicTable topics={limited} caption="Topics with too few posts this week to rank" />
        </section>
      )}
    </div>
  );
}