import { useEffect, useMemo, useRef, useState } from "react";
import {
  BrowserRouter,
  Routes,
  Route,
  Link,
  useLocation,
} from "react-router-dom";

import "./index.css";

import {
  getMeetings,
  getActionItems,
  updateActionItem,
  uploadMeeting,
  askQuestion,
  getApiError,
} from "./api/api";

/* =========================================================
   HELPERS
========================================================= */

function formatDate(date) {
  if (!date) return "Unknown date";

  try {
    return new Date(date).toLocaleDateString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  } catch {
    return String(date);
  }
}

function getMeetingTitle(meeting) {
  return meeting?.meeting_title || "Untitled Meeting";
}

function getMeetingId(meeting) {
  return meeting?._id || meeting?.id || "";
}

/* =========================================================
   LAYOUT
========================================================= */

function Layout({ children }) {
  const location = useLocation();

  const links = [
    { to: "/", label: "Dashboard" },
    { to: "/meetings", label: "Meetings" },
    { to: "/action-items", label: "Action Items" },
    { to: "/ask", label: "Ask AI" },
    { to: "/search", label: "Search" },
  ];

  return (
    <div className="app-layout">

      <aside className="sidebar">

        <div className="brand">
          <div className="brand-title">
            Meeting AI
          </div>

          <div className="brand-subtitle">
            Intelligence Assistant
          </div>
        </div>

        <div className="live-badge">
          <span className="live-dot"></span>
          Connected to FastAPI
        </div>

        <nav className="sidebar-nav">
          {links.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className={
                location.pathname === link.to
                  ? "active"
                  : ""
              }
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <div className="sidebar-bottom">
          <span>AI Meeting Intelligence</span>
          <small>FastAPI + MongoDB</small>
        </div>

      </aside>

      <main className="main-content">
        {children}
      </main>

    </div>
  );
}

/* =========================================================
   PAGE
========================================================= */

function Page({
  title,
  subtitle,
  children,
}) {
  return (
    <div className="page">

      <div className="page-header">
        <h1>{title}</h1>

        {subtitle && (
          <p className="page-subtitle">
            {subtitle}
          </p>
        )}
      </div>

      <div className="page-content">
        {children}
      </div>

    </div>
  );
}

/* =========================================================
   DASHBOARD
========================================================= */

function Dashboard() {
  const [meetings, setMeetings] = useState([]);
  const [actionItems, setActionItems] = useState([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    async function loadDashboard() {
      try {
        setLoading(true);
        setError("");

        const [
          meetingData,
          actionData,
        ] = await Promise.all([
          getMeetings(),
          getActionItems(),
        ]);

        console.log(
          "Dashboard meetings:",
          meetingData
        );

        console.log(
          "Dashboard action items:",
          actionData
        );

        setMeetings(
          Array.isArray(meetingData?.meetings)
            ? meetingData.meetings
            : []
        );

        setActionItems(
          Array.isArray(actionData?.action_items)
            ? actionData.action_items
            : []
        );

      } catch (err) {
        console.error(
          "Dashboard error:",
          err
        );

        setError(
          getApiError(
            err,
            "Could not load dashboard."
          )
        );

      } finally {
        setLoading(false);
      }
    }

    loadDashboard();
  }, []);

  const pending = actionItems.filter(
    (item) => item.status === "pending"
  ).length;

  const completed = actionItems.filter(
    (item) => item.status === "completed"
  ).length;

  const overdue = actionItems.filter(
    (item) => item.status === "overdue"
  ).length;

  if (loading) {
    return (
      <Page
        title="Dashboard"
        subtitle="Overview of your meeting intelligence."
      >
        <Loading message="Loading dashboard..." />
      </Page>
    );
  }

  if (error) {
    return (
      <Page title="Dashboard">
        <ErrorPanel message={error} />
      </Page>
    );
  }

  return (
    <Page
      title="Dashboard"
      subtitle="Overview of your meeting intelligence."
    >

      <div className="stats-grid">

        <StatCard
          label="Meetings"
          value={meetings.length}
        />

        <StatCard
          label="Action Items"
          value={actionItems.length}
        />

        <StatCard
          label="Pending"
          value={pending}
          tone="amber"
        />

        <StatCard
          label="Overdue"
          value={overdue}
          tone="brick"
        />

      </div>

      <div className="dashboard-grid">

        <div className="panel">

          <div className="panel-header">
            <h2>Recent Meetings</h2>

            <Link to="/meetings">
              View all
            </Link>
          </div>

          {meetings.length === 0 ? (
            <Empty message="No meetings found in MongoDB." />
          ) : (
            <div className="meeting-list">

              {meetings
                .slice(0, 5)
                .map((meeting) => (
                  <MeetingCard
                    key={getMeetingId(meeting)}
                    meeting={meeting}
                  />
                ))}

            </div>
          )}

        </div>

        <div className="panel">

          <div className="panel-header">
            <h2>Quick Actions</h2>
          </div>

          <div className="quick-actions">

            <Link to="/meetings">
              📋 View Meetings
            </Link>

            <Link to="/meetings">
              ⬆ Upload Meeting
            </Link>

            <Link to="/action-items">
              ✓ Action Items
            </Link>

            <Link to="/ask">
              🤖 Ask AI
            </Link>

            <Link to="/search">
              🔎 Search Meetings
            </Link>

          </div>

        </div>

      </div>

      <div className="panel dashboard-summary">

        <div className="panel-header">
          <h2>Action Item Summary</h2>
        </div>

        <div className="summary-row">
          <span>Pending</span>
          <strong>{pending}</strong>
        </div>

        <div className="summary-row">
          <span>Completed</span>
          <strong>{completed}</strong>
        </div>

        <div className="summary-row">
          <span>Overdue</span>
          <strong>{overdue}</strong>
        </div>

      </div>

    </Page>
  );
}

/* =========================================================
   MEETINGS
========================================================= */

function Meetings() {
  const [meetings, setMeetings] = useState([]);
  const [query, setQuery] = useState("");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState("");
  const [uploadError, setUploadError] = useState("");

  useEffect(() => {
    loadMeetings();
  }, []);

  async function loadMeetings() {
    try {
      setLoading(true);
      setError("");

      const data = await getMeetings();

      console.log(
        "Meetings page:",
        data
      );

      setMeetings(
        Array.isArray(data?.meetings)
          ? data.meetings
          : []
      );

    } catch (err) {
      console.error(
        "Meetings error:",
        err
      );

      setError(
        getApiError(
          err,
          "Could not load meetings."
        )
      );

    } finally {
      setLoading(false);
    }
  }

  async function handleUpload(event) {
    const file =
      event.target.files?.[0];

    if (!file) return;

    setUploading(true);
    setUploadMessage("");
    setUploadError("");

    try {
      await uploadMeeting(file);

      setUploadMessage(
        "Meeting uploaded and processed successfully."
      );

      await loadMeetings();

    } catch (err) {
      console.error(
        "Upload error:",
        err
      );

      setUploadError(
        getApiError(
          err,
          "Meeting upload failed."
        )
      );

    } finally {
      setUploading(false);

      event.target.value = "";
    }
  }

  const filtered = useMemo(() => {
    const q =
      query
        .toLowerCase()
        .trim();

    if (!q) return meetings;

    return meetings.filter(
      (meeting) => {
        const title =
          meeting?.meeting_title ||
          "";

        const summary =
          meeting?.summary ||
          "";

        return (
          title
            .toLowerCase()
            .includes(q) ||
          summary
            .toLowerCase()
            .includes(q)
        );
      }
    );
  }, [meetings, query]);

  return (
    <Page
      title="Meetings"
      subtitle="Upload, review and explore your processed meetings."
    >

      <div className="upload-panel">

        <div>
          <h2>Upload Meeting</h2>

          <p>
            Upload an MP3, WAV, M4A or OGG
            meeting recording.
          </p>
        </div>

        <label className="upload-button">

          {uploading
            ? "Processing..."
            : "⬆ Upload Meeting"}

          <input
            type="file"
            accept=".mp3,.wav,.m4a,.ogg,audio/*"
            onChange={handleUpload}
            disabled={uploading}
            hidden
          />

        </label>

      </div>

      {uploadMessage && (
        <div className="success-panel">
          {uploadMessage}
        </div>
      )}

      {uploadError && (
        <ErrorPanel message={uploadError} />
      )}

      <div className="search-box">

        <input
          type="text"
          placeholder="Search meetings..."
          value={query}
          onChange={(e) =>
            setQuery(e.target.value)
          }
        />

      </div>

      {loading && (
        <div className="panel">
          <Loading message="Loading meetings..." />
        </div>
      )}

      {error && (
        <ErrorPanel message={error} />
      )}

      {!loading && !error && (
        <div className="panel">

          <div className="panel-header">

            <h2>
              Meetings

              <span className="count-badge">
                {filtered.length}
              </span>
            </h2>

          </div>

          {filtered.length === 0 ? (
            <Empty message="No meetings found." />
          ) : (
            <div className="meeting-list">

              {filtered.map(
                (meeting) => (
                  <MeetingCard
                    key={getMeetingId(meeting)}
                    meeting={meeting}
                  />
                )
              )}

            </div>
          )}

        </div>
      )}

    </Page>
  );
}

/* =========================================================
   MEETING CARD
========================================================= */

function MeetingCard({ meeting }) {
  const [open, setOpen] =
    useState(false);

  const actions =
    Array.isArray(
      meeting?.action_items
    )
      ? meeting.action_items
      : [];

  const decisions =
    Array.isArray(
      meeting?.decisions
    )
      ? meeting.decisions
      : [];

  const topics =
    Array.isArray(
      meeting?.topics
    )
      ? meeting.topics
      : [];

  const keyPoints =
    Array.isArray(
      meeting?.key_points
    )
      ? meeting.key_points
      : [];

  const questions =
    Array.isArray(
      meeting?.open_questions
    )
      ? meeting.open_questions
      : [];

  return (
    <div
      className={`meeting-card ${
        open ? "open" : ""
      }`}
    >

      <button
        type="button"
        className="meeting-row"
        onClick={() =>
          setOpen(
            (value) => !value
          )
        }
      >

        <span className="expand-icon">
          {open ? "▼" : "▶"}
        </span>

        <div className="meeting-row-main">

          <strong>
            {getMeetingTitle(meeting)}
          </strong>

          <span className="meta">
            {formatDate(
              meeting?.uploaded_at
            )}

            {" · "}

            {actions.length} action item
            {actions.length !== 1
              ? "s"
              : ""}
          </span>

        </div>

        <span className="badge processed">
          Processed
        </span>

      </button>

      {open && (
        <div className="meeting-detail">

          <section>
            <h4>Summary</h4>

            <p>
              {meeting?.summary ||
                "No summary available."}
            </p>
          </section>

          {topics.length > 0 && (
            <section>
              <h4>Topics</h4>

              <ul>
                {topics.map(
                  (topic, index) => (
                    <li key={index}>
                      {topic}
                    </li>
                  )
                )}
              </ul>
            </section>
          )}

          {keyPoints.length > 0 && (
            <section>
              <h4>Key Points</h4>

              <ul>
                {keyPoints.map(
                  (point, index) => (
                    <li key={index}>
                      {point}
                    </li>
                  )
                )}
              </ul>
            </section>
          )}

          {decisions.length > 0 && (
            <section>
              <h4>Decisions</h4>

              <ul>
                {decisions.map(
                  (decision, index) => (
                    <li key={index}>
                      {decision}
                    </li>
                  )
                )}
              </ul>
            </section>
          )}

          {actions.length > 0 && (
            <section>
              <h4>Action Items</h4>

              <ul>
                {actions.map(
                  (action, index) => (
                    <li key={index}>

                      <strong>
                        {action?.task ||
                          "Task not specified"}
                      </strong>

                      {" — "}

                      {action?.owner ||
                        "Not specified"}

                      {" · due "}

                      {action?.due_date ||
                        "Not specified"}

                    </li>
                  )
                )}
              </ul>
            </section>
          )}

          {questions.length > 0 && (
            <section>
              <h4>Open Questions</h4>

              <ul>
                {questions.map(
                  (question, index) => (
                    <li key={index}>
                      {question}
                    </li>
                  )
                )}
              </ul>
            </section>
          )}

        </div>
      )}

    </div>
  );
}

/* =========================================================
   ACTION ITEMS
========================================================= */

function ActionItems() {
  const [items, setItems] =
    useState([]);

  const [filter, setFilter] =
    useState("all");

  const [loading, setLoading] =
    useState(true);

  const [error, setError] =
    useState("");

  const [updating, setUpdating] =
    useState("");

  useEffect(() => {
    loadItems();
  }, []);

  async function loadItems() {
    try {
      setLoading(true);
      setError("");

      const data =
        await getActionItems();

      console.log(
        "Action items:",
        data
      );

      setItems(
        Array.isArray(
          data?.action_items
        )
          ? data.action_items
          : []
      );

    } catch (err) {
      console.error(
        "Action items error:",
        err
      );

      setError(
        getApiError(
          err,
          "Could not load action items."
        )
      );

    } finally {
      setLoading(false);
    }
  }

  const counts = {
    all: items.length,

    pending:
      items.filter(
        (item) =>
          item.status === "pending"
      ).length,

    completed:
      items.filter(
        (item) =>
          item.status === "completed"
      ).length,

    overdue:
      items.filter(
        (item) =>
          item.status === "overdue"
      ).length,
  };

  const visible =
    items.filter((item) => {

      if (filter === "pending") {
        return (
          item.status === "pending"
        );
      }

      if (filter === "completed") {
        return (
          item.status === "completed"
        );
      }

      if (filter === "overdue") {
        return (
          item.status === "overdue"
        );
      }

      return true;
    });

  async function toggleItem(item) {
    const newStatus =
      item.status === "completed"
        ? "pending"
        : "completed";

    /*
      IMPORTANT:

      Prefer action_index from the backend.

      If your backend does not yet provide
      action_index, use item.index.

      We do NOT use the flattened array index.
    */

    const actionIndex =
      item.action_index ??
      item.index;

    if (
      actionIndex === undefined ||
      actionIndex === null
    ) {
      alert(
        "This action item does not contain an action_index. Update your /action-items endpoint to include it."
      );

      return;
    }

    const updateKey =
      `${item.meeting_id}-${actionIndex}`;

    try {
      setUpdating(updateKey);

      await updateActionItem(
        item.meeting_id,
        actionIndex,
        newStatus
      );

      /*
        Update frontend immediately.
      */

      setItems((current) =>
        current.map((currentItem) => {

          const currentIndex =
            currentItem.action_index ??
            currentItem.index;

          if (
            String(
              currentItem.meeting_id
            ) ===
              String(
                item.meeting_id
              ) &&
            Number(currentIndex) ===
              Number(actionIndex)
          ) {
            return {
              ...currentItem,
              status: newStatus,
            };
          }

          return currentItem;
        })
      );

    } catch (err) {

      console.error(
        "Could not update action item:",
        err
      );

      /*
        IMPORTANT:

        Never do:
        alert(err.response.data)

        because that creates:
        [object Object]

        Use getApiError().
      */

      alert(
        getApiError(
          err,
          "Could not update action item."
        )
      );

    } finally {
      setUpdating("");
    }
  }

  if (loading) {
    return (
      <Page
        title="Action Items"
        subtitle="Track tasks extracted from your meetings."
      >
        <div className="panel">
          <Loading message="Loading action items..." />
        </div>
      </Page>
    );
  }

  if (error) {
    return (
      <Page title="Action Items">
        <ErrorPanel message={error} />
      </Page>
    );
  }

  return (
    <Page
      title="Action Items"
      subtitle="Track tasks extracted from your meetings."
    >

      <div className="tab-row">

        {[
          "all",
          "pending",
          "completed",
          "overdue",
        ].map((filterName) => (

          <button
            type="button"
            key={filterName}
            className={`tab ${
              filter === filterName
                ? "active"
                : ""
            }`}
            onClick={() =>
              setFilter(filterName)
            }
          >

            {filterName
              .charAt(0)
              .toUpperCase() +
              filterName.slice(1)}

            <span className="tab-count">
              {counts[filterName]}
            </span>

          </button>

        ))}

      </div>

      <div className="panel">

        {visible.length === 0 ? (
          <Empty message="No action items here." />
        ) : (

          <div className="action-list">

            {visible.map(
              (item, displayIndex) => {

                const actionIndex =
                  item.action_index ??
                  item.index;

                const updateKey =
                  `${item.meeting_id}-${actionIndex}`;

                const isUpdating =
                  updating === updateKey;

                return (
                  <div
                    className={`action-row ${
                      item.status ===
                      "completed"
                        ? "done"
                        : ""
                    }`}
                    key={
                      `${item.meeting_id}-${actionIndex}-${displayIndex}`
                    }
                  >

                    <input
                      type="checkbox"
                      checked={
                        item.status ===
                        "completed"
                      }
                      disabled={
                        isUpdating ||
                        actionIndex ===
                          undefined
                      }
                      onChange={() =>
                        toggleItem(item)
                      }
                    />

                    <div className="action-main">

                      <span className="action-text">

                        {item.task ||
                          "Task not specified"}

                      </span>

                      <span className="action-meta">

                        {item.meeting_title ||
                          "Unknown meeting"}

                        {" · "}

                        {item.owner ||
                          "Not specified"}

                        {" · due "}

                        {item.due_date ||
                          "Not specified"}

                      </span>

                    </div>

                    {isUpdating ? (

                      <span className="priority priority-updating">
                        Updating...
                      </span>

                    ) : (

                      <span
                        className={`priority ${
                          item.status ===
                          "completed"
                            ? "priority-low"
                            : item.status ===
                              "overdue"
                            ? "priority-overdue"
                            : "priority-high"
                        }`}
                      >
                        {item.status ||
                          "pending"}
                      </span>

                    )}

                  </div>
                );
              }
            )}

          </div>

        )}

      </div>

    </Page>
  );
}

/* =========================================================
   ASK AI
========================================================= */

function AskAI() {
  const [messages, setMessages] = useState([
    {
      id: crypto.randomUUID(),
      role: "ai",
      text: "Hello! Ask me anything about your meetings, decisions, action items, topics, or deadlines.",
    },
  ]);
  const [question, setQuestion] = useState("");
  const [thinking, setThinking] = useState(false);
  const chatEndRef = useRef(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, thinking]);

  async function ask() {
    const q = question.trim();

    if (!q || thinking) return;

    setMessages((previous) => [
      ...previous,
      { id: crypto.randomUUID(), role: "user", text: q },
    ]);
    setQuestion("");
    setThinking(true);

    try {
      const response = await askQuestion(q);
      const answer =
        response?.answer ||
        response?.response ||
        response?.result ||
        "I couldn't find an answer.";

      setMessages((previous) => [
        ...previous,
        { id: crypto.randomUUID(), role: "ai", text: answer },
      ]);
    } catch (err) {
      console.error("Ask AI error:", err);
      setMessages((previous) => [
        ...previous,
        {
          id: crypto.randomUUID(),
          role: "ai",
          text: `Sorry, something went wrong: ${getApiError(err, "Could not connect to the AI service.")}`,
          error: true,
        },
      ]);
    } finally {
      setThinking(false);
    }
  }

  return (
    <Page
      title="Ask AI"
      subtitle="Ask questions about your stored meeting data."
    >

      <div className="panel ask-panel">

        <div className="chat-area">

          {messages.map((message) => (
            <div
              key={message.id}
              className={`chat-message ${message.role === "user" ? "user-message" : "ai-message"}`}
            >
              <div className="chat-label">
                {message.role === "user" ? "You" : "AI"}
              </div>
              <div className={`chat-bubble ${message.role === "user" ? "user" : "ai"} ${message.error ? "chat-error" : ""}`}>
                {message.text}
              </div>
            </div>
          ))}

          {thinking && (
            <div className="chat-message ai-message">
              <div className="chat-label">AI</div>
              <div className="chat-bubble ai thinking" aria-label="AI is thinking">
                <span className="thinking-dot"></span>
                <span className="thinking-dot"></span>
                <span className="thinking-dot"></span>
              </div>
            </div>
          )}

          <div ref={chatEndRef} />

        </div>

        <div className="ask-box">

          <input
            type="text"
            placeholder="Ask something about your meetings..."
            value={question}
            onChange={(e) =>
              setQuestion(e.target.value)
            }
            onKeyDown={(e) => {
              if (
                e.key === "Enter" &&
                !e.shiftKey
              ) {
                e.preventDefault();
                ask();
              }
            }}
            disabled={thinking}
          />

          <button
            type="button"
            onClick={ask}
            disabled={thinking || !question.trim()}
          >
            {thinking ? "Thinking..." : "Ask AI"}
          </button>

        </div>

      </div>

    </Page>
  );
}

/* =========================================================
   SEARCH
========================================================= */

function Search() {
  const [meetings, setMeetings] =
    useState([]);

  const [query, setQuery] =
    useState("");

  const [loading, setLoading] =
    useState(true);

  useEffect(() => {
    async function load() {
      try {
        const data =
          await getMeetings();

        setMeetings(
          Array.isArray(
            data?.meetings
          )
            ? data.meetings
            : []
        );

      } catch (err) {
        console.error(
          "Search error:",
          err
        );
      } finally {
        setLoading(false);
      }
    }

    load();
  }, []);

  const results =
    useMemo(() => {

      if (!query.trim()) {
        return [];
      }

      const q =
        query
          .toLowerCase()
          .trim();

      return meetings.filter(
        (meeting) => {

          const title =
            meeting?.meeting_title ||
            "";

          const summary =
            meeting?.summary ||
            "";

          const topics =
            Array.isArray(
              meeting?.topics
            )
              ? meeting.topics.join(
                  " "
                )
              : "";

          const decisions =
            Array.isArray(
              meeting?.decisions
            )
              ? meeting.decisions.join(
                  " "
                )
              : "";

          const keyPoints =
            Array.isArray(
              meeting?.key_points
            )
              ? meeting.key_points.join(
                  " "
                )
              : "";

          return (
            title
              .toLowerCase()
              .includes(q) ||
            summary
              .toLowerCase()
              .includes(q) ||
            topics
              .toLowerCase()
              .includes(q) ||
            decisions
              .toLowerCase()
              .includes(q) ||
            keyPoints
              .toLowerCase()
              .includes(q)
          );
        }
      );

    }, [meetings, query]);

  return (
    <Page
      title="Search"
      subtitle="Search across your stored meetings."
    >

      <div className="search-box">

        <input
          type="text"
          placeholder="Search your meetings..."
          value={query}
          onChange={(e) =>
            setQuery(e.target.value)
          }
        />

      </div>

      <div className="panel">

        {loading && (
          <Loading message="Loading meeting data..." />
        )}

        {!loading &&
          !query && (
            <Empty message="Search across your meetings." />
          )}

        {!loading &&
          query &&
          results.length === 0 && (
            <Empty
              message={`No results for "${query}".`}
            />
          )}

        {!loading &&
          results.length > 0 && (

            <div className="search-results">

              {results.map(
                (meeting) => (

                  <div
                    className="search-result"
                    key={getMeetingId(
                      meeting
                    )}
                  >

                    <div className="search-result-head">

                      <strong>
                        {getMeetingTitle(
                          meeting
                        )}
                      </strong>

                      <span className="meta">
                        {formatDate(
                          meeting.uploaded_at
                        )}
                      </span>

                    </div>

                    <p>
                      {meeting.summary ||
                        "No summary available."}
                    </p>

                  </div>

                )
              )}

            </div>

          )}

      </div>

    </Page>
  );
}

/* =========================================================
   SHARED COMPONENTS
========================================================= */

function StatCard({
  label,
  value,
  tone = "default",
}) {
  return (
    <div
      className={`stat-card tone-${tone}`}
    >

      <span className="stat-label">
        {label}
      </span>

      <strong className="stat-value">
        {value}
      </strong>

    </div>
  );
}

function Empty({ message }) {
  return (
    <div className="empty">
      {message}
    </div>
  );
}

function Loading({ message }) {
  return (
    <div className="loading">
      <div className="spinner"></div>
      <span>{message}</span>
    </div>
  );
}

function ErrorPanel({ message }) {
  return (
    <div className="panel error-panel">
      <strong>
        Something went wrong
      </strong>

      <p>{String(message)}</p>
    </div>
  );
}

/* =========================================================
   APP
========================================================= */

function App() {
  return (
    <BrowserRouter>

      <Layout>

        <Routes>

          <Route
            path="/"
            element={<Dashboard />}
          />

          <Route
            path="/meetings"
            element={<Meetings />}
          />

          <Route
            path="/action-items"
            element={<ActionItems />}
          />

          <Route
            path="/ask"
            element={<AskAI />}
          />

          <Route
            path="/search"
            element={<Search />}
          />

        </Routes>

      </Layout>

    </BrowserRouter>
  );
}

export default App;
