/**
 * Saved assessment sessions, newest first.
 *
 * Sessions accumulate from the first one, so this page exists as soon as there
 * is anything to show. It lists what each session recorded and can open one in
 * full.
 *
 * What it deliberately does not do is compare sessions. Two recordings made on
 * different days in different rooms, with different camera positions and
 * different clothing, differ for reasons that have nothing to do with the
 * person. Drawing a trend line through them would imply a precision that a
 * webcam in an uncontrolled setting does not have.
 */

import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import { StatusPill } from "../assessment/components/Feedback.jsx";
import SessionResults, {
  SessionSummaryLine,
} from "../assessment/components/SessionResults.jsx";
import { TEST_ORDER, TEST_TITLES } from "../assessment/config/protocol.js";
import { fetchAssessment, fetchAssessmentHistory } from "../services/assessments";
import { getToken } from "../services/auth";

// SessionResults uses the assess-* classes defined alongside the assessment
// flow. Imported here so the shared component looks the same on both pages.
import "./AssessmentPage.css";
import "./HistoryPage.css";

const PAGE_SIZE = 10;

function formatDate(value) {
  if (!value) return "Unknown date";

  return new Date(value).toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function HistoryPage() {
  const navigate = useNavigate();

  const signedIn = Boolean(getToken());

  const [sessions, setSessions] = useState([]);
  const [total, setTotal] = useState(0);
  const [listState, setListState] = useState(() => (signedIn ? "loading" : "signed-out"));
  const [listError, setListError] = useState(null);

  const [openId, setOpenId] = useState(null);
  const [openSession, setOpenSession] = useState(null);
  const [detailState, setDetailState] = useState("idle");
  const [detailError, setDetailError] = useState(null);

  const loadPage = useCallback(
    async (skip) => {
      setListState(skip === 0 ? "loading" : "loading-more");
      setListError(null);

      try {
        const page = await fetchAssessmentHistory({ limit: PAGE_SIZE, skip });

        setSessions((current) =>
          skip === 0 ? page.assessments : [...current, ...page.assessments]
        );
        setTotal(page.total);
        setListState("ready");
      } catch (error) {
        setListError(error.message);
        setListState("error");
      }
    },
    []
  );

  useEffect(() => {
    if (!signedIn) {
      return;
    }

    let ignore = false;

    fetchAssessmentHistory({ limit: PAGE_SIZE, skip: 0 })
      .then((page) => {
        if (!ignore) {
          setSessions(page.assessments);
          setTotal(page.total);
          setListState("ready");
        }
      })
      .catch((error) => {
        if (!ignore) {
          setListError(error.message);
          setListState("error");
        }
      });

    return () => {
      ignore = true;
    };
  }, [signedIn]);

  async function openSessionDetail(assessmentId) {
    // A second click on the same row closes it, so the list stays usable
    // without a separate back step.
    if (openId === assessmentId) {
      setOpenId(null);
      setOpenSession(null);
      setDetailState("idle");

      return;
    }

    setOpenId(assessmentId);
    setOpenSession(null);
    setDetailState("loading");
    setDetailError(null);

    try {
      const assessment = await fetchAssessment(assessmentId);

      setOpenSession(assessment);
      setDetailState("ready");
    } catch (error) {
      setDetailError(error.message);
      setDetailState("error");
    }
  }

  const hasMore = sessions.length < total;

  return (
    <div className="history-page">
      <header className="assess-header">
        <button
          type="button"
          className="assess-header__logo"
          onClick={() => navigate("/dashboard")}
        >
          <span className="assess-header__mark">M</span>
          <span>
            MoveWell<small>AI</small>
          </span>
        </button>

        <span className="assess-header__title">Your sessions</span>

        <button
          type="button"
          className="assess-btn assess-btn--quiet"
          onClick={() => navigate("/dashboard")}
        >
          Dashboard
        </button>
      </header>

      <main className="history-main">
        <div className="history-intro">
          <span className="history-eyebrow">MOVEMENT CHECKS</span>
          <h1>Every session you have saved</h1>
          <p>
            Each session is kept exactly as it was recorded. Sessions are not
            averaged or combined, and no trend is drawn between them: recordings
            made on different days, in different rooms, with the camera in a
            different place are not precise enough to support that.
          </p>
        </div>

        {listState === "signed-out" && (
          <p className="history-empty">
            Sign in to see your saved sessions.
          </p>
        )}

        {listState === "loading" && (
          <p className="history-empty">Loading your sessions…</p>
        )}

        {listState === "error" && (
          <div className="history-empty">
            <p>Your sessions could not be loaded. {listError}</p>
            <button
              type="button"
              className="assess-btn assess-btn--ghost"
              onClick={() => loadPage(0)}
            >
              Try again
            </button>
          </div>
        )}

        {listState !== "loading" &&
          listState !== "signed-out" &&
          listState !== "error" &&
          sessions.length === 0 && (
            <div className="history-empty">
              <p>
                You have not saved a session yet. Nothing is shown here until you
                complete a movement check and save it.
              </p>
              <button
                type="button"
                className="assess-btn assess-btn--primary"
                onClick={() => navigate("/assessment")}
              >
                Start a check
              </button>
            </div>
          )}

        {sessions.length > 0 && (
          <>
            <p className="history-count">
              {total} {total === 1 ? "session" : "sessions"} saved
            </p>

            <ol className="history-list">
              {sessions.map((entry) => {
                const open = openId === entry.id;

                return (
                  <li className="history-item" key={entry.id}>
                    <button
                      type="button"
                      className="history-item__head"
                      aria-expanded={open}
                      onClick={() => openSessionDetail(entry.id)}
                    >
                      <span className="history-item__date">
                        {formatDate(entry.startedAt)}
                      </span>

                      <span className="history-item__statuses">
                        {TEST_ORDER.map((testId) => (
                          <span className="history-item__status" key={testId}>
                            <span className="history-item__test">
                              {TEST_TITLES[testId]}
                            </span>
                            <StatusPill status={entry.statuses?.[testId] ?? "not_started"} />
                          </span>
                        ))}
                      </span>

                      <span className="history-item__toggle">
                        {open ? "Hide" : "View"}
                      </span>
                    </button>

                    {open && (
                      <div className="history-item__body">
                        {detailState === "loading" && (
                          <p className="history-empty">Loading this session…</p>
                        )}

                        {detailState === "error" && (
                          <p className="history-empty">
                            This session could not be loaded. {detailError}
                          </p>
                        )}

                        {detailState === "ready" && openSession && (
                          <>
                            <SessionSummaryLine summary={openSession.summary} />
                            <SessionResults session={openSession} />
                          </>
                        )}
                      </div>
                    )}
                  </li>
                );
              })}
            </ol>

            {hasMore && (
              <button
                type="button"
                className="assess-btn assess-btn--ghost"
                disabled={listState === "loading-more"}
                onClick={() => loadPage(sessions.length)}
              >
                {listState === "loading-more" ? "Loading…" : "Load older sessions"}
              </button>
            )}
          </>
        )}
      </main>
    </div>
  );
}

export default HistoryPage;
