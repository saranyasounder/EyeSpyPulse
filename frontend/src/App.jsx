import { useEffect, useState } from "react";
import FrictionSnapshot from "./components/FrictionSnapshot";
import UrgencyBarChart from "./components/UrgencyBarChart";
import TopicsTable from "./components/TopicsTable";
import { fetchCurrentTopics } from "./api";

const STALE_AFTER_DAYS = 2;

function Logo() {
  return (
    <svg width="32" height="32" viewBox="0 0 32 32" aria-hidden="true">
      <circle cx="16" cy="16" r="15" fill="none" stroke="currentColor" strokeWidth="2" />
      <circle cx="16" cy="16" r="6" fill="currentColor" />
    </svg>
  );
}

export default function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchCurrentTopics().then(setData).catch((e) => setError(e.message));
  }, []);

  const isStale =
    data?.as_of &&
    (Date.now() - new Date(data.as_of).getTime()) / 86400000 > STALE_AFTER_DAYS;

  return (
    <>
      <a className="skip-link" href="#main">
        Skip to content
      </a>

      <header className="site-header">
        <Logo />
        <div>
          <h1>
            ES<span className="accent-dot">-</span>Pulse
          </h1>
          <p className="tagline">Community friction, surfaced daily</p>
        </div>
      </header>

      <main id="main">
        {error && (
          <p role="alert" className="error-notice">
            Couldn't load today's data: {error}
          </p>
        )}

        {isStale && (
          <p className="stale-notice" role="status">
            This data hasn't updated in over {STALE_AFTER_DAYS} days — the
            daily pipeline may not have run.
          </p>
        )}

        {data && (
          <>
            <FrictionSnapshot topics={data.topics} asOf={data.as_of} />
            <UrgencyBarChart topics={data.topics} />
            <TopicsTable topics={data.topics} />
            <p className="footnote">
              Trends compare today's score with the previous three days and
              update each morning. A topic needs at least 3 posts this week
              to be ranked or show a trend.
            </p>
          </>
        )}
      </main>
    </>
  );
}