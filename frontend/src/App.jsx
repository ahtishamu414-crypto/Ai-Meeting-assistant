import {
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
 
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
  getMeeting,
  getActionItems,
  updateActionItem,
  askQuestion,
  searchMeetings,
  uploadRecording,
  getSlackMeetings,
  getSlackMeeting,
  formatDate,
  getApiError,
} from "./api/api";
 
/* =========================================================
   HELPERS
========================================================= */
 
function getMeetingId(meeting) {
  return String(
    meeting?._id || meeting?.id || meeting?.meeting_id || ""
  ).trim();
}
 
function getMeetingTitle(meeting) {
  return meeting?.meeting_title || meeting?.title || "Untitled Meeting";
}
 
function normalizeMeetings(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.meetings)) return data.meetings;
  return [];
}
 
function normalizeActionItems(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.action_items)) return data.action_items;
  return [];
}
 
function normalizeSearchResults(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.results)) return data.results;
  if (Array.isArray(data?.meetings)) return data.meetings;
  return [];
}
 
function getAnswer(data) {
  if (typeof data === "string") return data;
  if (!data) return "No answer returned.";
  if (typeof data?.answer === "string") return data.answer;
  if (typeof data?.response === "string") return data.response;
  if (typeof data?.result === "string") return data.result;
  if (typeof data?.message === "string") return data.message;
  return "I could not find an answer in the provided meeting context.";
}
 
function isOverdue(item) {
  if (!item?.due_date) return item?.status === "overdue";
  if (item?.status === "completed") return false;
  const due = new Date(item.due_date);
  if (Number.isNaN(due.getTime())) return item?.status === "overdue";
  return due < new Date();
}
 
/*
  IMPORTANT:
  Prefer the backend's action_index.
  Only calculate one if the backend does not provide it.
*/
function getActionIndex(item, fallbackIndex = 0) {
  const backendIndex = item?.action_index ?? item?.actionIndex ?? item?.index;
  if (backendIndex !== undefined && backendIndex !== null && backendIndex !== "") {
    const number = Number(backendIndex);
    if (Number.isInteger(number)) return number;
  }
  return fallbackIndex;
}
 
function initials(text) {
  if (!text) return "?";
  const parts = String(text).trim().split(/\s+/).slice(0, 2);
  return parts.map((p) => p[0]?.toUpperCase() || "").join("") || "?";
}
 
function timeAgo(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  if (Number.isNaN(d.getTime())) return "";
  const diffMs = Date.now() - d.getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return formatDate(dateStr);
}
 
/* =========================================================
   WAVEFORM — signature motif, reused across the app
========================================================= */
 
function Waveform({
  bars = 24,
  active = false,
  tone = "teal",
  size = "md",
}) {
  const heights = useMemo(
    () =>
      Array.from({ length: bars }, (_, i) => {
        // deterministic pseudo-random pattern so it doesn't reflow on re-render
        const seed = Math.sin(i * 12.9898) * 43758.5453;
        return 20 + Math.abs(seed % 1) * 80;
      }),
    [bars]
  );
 
  return (
    <div
      className={`waveform waveform-${size} waveform-${tone} ${
        active ? "waveform-active" : ""
      }`}
      aria-hidden="true"
    >
      {heights.map((h, i) => (
        <span
          key={i}
          style={{
            height: `${h}%`,
            animationDelay: `${(i % 8) * 0.07}s`,
          }}
        />
      ))}
    </div>
  );
}
 
/* =========================================================
   TOAST SYSTEM
========================================================= */
 
function useToasts() {
  const [toasts, setToasts] = useState([]);
 
  function push(text, tone = "default") {
    const id = `t-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    setToasts((current) => [...current, { id, text, tone }]);
    window.setTimeout(() => {
      setToasts((current) => current.filter((t) => t.id !== id));
    }, 4200);
  }
 
  function dismiss(id) {
    setToasts((current) => current.filter((t) => t.id !== id));
  }
 
  return { toasts, push, dismiss };
}
 
function ToastStack({ toasts, onDismiss }) {
  if (!toasts.length) return null;
 
  return (
    <div className="toast-stack">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast toast-${toast.tone}`}>
          <span>{toast.text}</span>
          <button type="button" onClick={() => onDismiss(toast.id)}>
            ✕
          </button>
        </div>
      ))}
    </div>
  );
}
 
/* =========================================================
   LAYOUT
========================================================= */
 
function Layout({ children }) {
  const location = useLocation();
 
  const links = [
    { to: "/", label: "Dashboard", icon: "▦" },
    { to: "/meetings", label: "Meetings", icon: "◫" },
    { to: "/slack-meetings", label: "Slack Meetings", icon: "◈" },
    { to: "/action-items", label: "Action Items", icon: "✓" },
    { to: "/ask", label: "Ask AI", icon: "✦" },
    { to: "/search", label: "Semantic Search", icon: "⌕" },
  ];
 
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <Waveform bars={5} active size="xs" tone="teal" />
          </div>
          <div>
            <strong>Meeting AI</strong>
            <span>Intelligence Assistant</span>
          </div>
        </div>
 
        <div className="live-badge">
          <span className="live-dot" />
          Connected to FastAPI
        </div>
 
        <nav className="sidebar-nav">
          {links.map((link) => (
            <Link
              key={link.to}
              to={link.to}
              className={location.pathname === link.to ? "active" : ""}
            >
              <span className="nav-icon">{link.icon}</span>
              <span>{link.label}</span>
            </Link>
          ))}
        </nav>
 
        <div className="sidebar-waveform">
          <Waveform bars={40} tone="dim" size="sm" />
        </div>
 
        <div className="sidebar-bottom">
          <strong>AI Meeting Intelligence</strong>
          <small>FastAPI + MongoDB</small>
        </div>
      </aside>
 
      <main className="main-content">{children}</main>
    </div>
  );
}
 
/* =========================================================
   PAGE
========================================================= */
 
function Page({ title, subtitle, actions, children }) {
  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1>{title}</h1>
          {subtitle && <p className="page-subtitle">{subtitle}</p>}
        </div>
        {actions && <div className="page-actions">{actions}</div>}
      </div>
      <div className="page-content">{children}</div>
    </div>
  );
}
 
/* =========================================================
   LOADING / ERROR / EMPTY
========================================================= */
 
function Loading({ message = "Loading..." }) {
  return (
    <div className="panel loading-panel">
      <Waveform bars={16} active tone="teal" size="sm" />
      <span>{message}</span>
    </div>
  );
}
 
function ErrorPanel({ message, onRetry }) {
  return (
    <div className="panel error-panel">
      <div className="error-icon">!</div>
      <div>
        <strong>Something went wrong</strong>
        <p>{message}</p>
      </div>
      {onRetry && (
        <button type="button" className="ghost-button" onClick={onRetry}>
          Try again
        </button>
      )}
    </div>
  );
}
 
function Empty({ message, icon = "◌" }) {
  return (
    <div className="empty-state">
      <div className="empty-icon">{icon}</div>
      <p>{message}</p>
    </div>
  );
}
 
/* =========================================================
   STAT CARD — now with trend + sparkline
========================================================= */
 
function StatCard({ label, value, tone = "default", icon, trend }) {
  return (
    <div className={`stat-card tone-${tone}`}>
      <div className="stat-top">
        <span>{label}</span>
        <span className="stat-icon">{icon}</span>
      </div>
 
      <div className="stat-bottom">
        <strong className="stat-value">{value}</strong>
        {trend !== undefined && trend !== null && (
          <span className={`stat-trend ${trend >= 0 ? "up" : "down"}`}>
            {trend >= 0 ? "▲" : "▼"} {Math.abs(trend)}%
          </span>
        )}
      </div>
 
      <div className="stat-accent-bar" />
    </div>
  );
}
 
/* =========================================================
   UPLOAD PANEL
========================================================= */
 
function UploadPanel({ onUploaded, pushToast }) {
  const inputRef = useRef(null);
  const dropRef = useRef(null);
 
  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [progress, setProgress] = useState(0);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);
 
  function chooseFile(selected) {
    if (!selected) return;
    setFile(selected);
    setMessage("");
    setError("");
    setProgress(0);
  }
 
  function onInputChange(event) {
    chooseFile(event.target.files?.[0]);
  }
 
  function onDrop(event) {
    event.preventDefault();
    setDragOver(false);
    chooseFile(event.dataTransfer.files?.[0]);
  }
 
  async function handleUpload() {
    if (!file || uploading) return;
 
    setUploading(true);
    setError("");
    setMessage("");
    setProgress(0);
 
    try {
      const result = await uploadRecording(file, (event) => {
        if (event.total) {
          setProgress(Math.round((event.loaded / event.total) * 100));
        }
      });
 
      setProgress(100);
      const successMsg = result?.message || "Meeting processed successfully.";
      setMessage(successMsg);
      pushToast?.(successMsg, "success");
      setFile(null);
 
      if (inputRef.current) inputRef.current.value = "";
      if (onUploaded) onUploaded(result);
    } catch (err) {
      console.error("Upload error:", err);
      const msg = getApiError(err, "Meeting upload failed.");
      setError(msg);
      pushToast?.(msg, "error");
    } finally {
      setUploading(false);
    }
  }
 
  return (
    <div
      className={`upload-panel ${dragOver ? "drag-over" : ""}`}
      ref={dropRef}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={onDrop}
    >
      <div className="upload-info">
        <div className="upload-icon">↑</div>
        <div>
          <h3>Upload a meeting recording</h3>
          <p>
            Drop an MP3, WAV, M4A or OGG file, or browse. Whisper transcribes
            the recording and the AI pipeline extracts the meeting data.
          </p>
        </div>
      </div>
 
      <div className="upload-controls">
        <input
          ref={inputRef}
          type="file"
          accept=".mp3,.wav,.m4a,.ogg,audio/*"
          onChange={onInputChange}
          disabled={uploading}
        />
 
        <button
          type="button"
          className="primary-button"
          onClick={handleUpload}
          disabled={!file || uploading}
        >
          {uploading ? "Processing..." : "Upload & Process"}
        </button>
      </div>
 
      {file && (
        <div className="selected-file">
          <span className="file-chip">
            <span className="file-chip-icon">♪</span>
            {file.name}
          </span>
          <span>{(file.size / 1024 / 1024).toFixed(2)} MB</span>
        </div>
      )}
 
      {uploading && (
        <div className="progress-wrapper">
          <Waveform bars={20} active tone="teal" size="xs" />
          <div className="progress-bar">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <span>{progress}%</span>
        </div>
      )}
 
      {message && <div className="success-message">✓ {message}</div>}
      {error && <div className="error-message">{error}</div>}
    </div>
  );
}
 
/* =========================================================
   SLACK MEETINGS
========================================================= */

function formatHuddleDuration(seconds) {
  if (!Number.isFinite(seconds) || seconds <= 0) return "—";
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  if (mins === 0) return `${secs}s`;
  return `${mins}m ${secs}s`;
}

function SlackMeetings() {
  const [meetings, setMeetings] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadMeetings() {
    try {
      setLoading(true);
      setError("");

      const data = await getSlackMeetings();
      const list = Array.isArray(data?.meetings) ? data.meetings : [];
      setMeetings(list);
    } catch (err) {
      console.error("Slack meetings error:", err);
      setError(getApiError(err, "Could not load Slack meetings."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    queueMicrotask(loadMeetings);

    const interval = setInterval(loadMeetings, 10000);

    return () => clearInterval(interval);
  }, []);

  if (loading && meetings.length === 0 && !error) {
    return (
      <div className="panel slack-meetings">
        <div className="panel-header">
          <h2>Slack Meetings</h2>
        </div>

        <Loading message="Checking Slack Huddles..." />
      </div>
    );
  }

  if (error) {
    return (
      <div className="panel slack-meetings">
        <div className="panel-header">
          <h2>Slack Meetings</h2>
        </div>

        <ErrorPanel message={error} onRetry={loadMeetings} />
      </div>
    );
  }

  const activeCount = meetings.filter((m) => m.status === "active").length;

  return (
    <div className="panel slack-meetings">
      <div className="panel-header">
        <div>
          <h2>Slack Meetings</h2>
          <p className="panel-subtitle">
            {activeCount > 0
              ? `${activeCount} Huddle${activeCount === 1 ? "" : "s"} in progress`
              : "Slack Huddle processing pipeline"}
          </p>
        </div>

        <button type="button" className="secondary-button" onClick={loadMeetings}>
          ↻ Refresh
        </button>
      </div>

      {meetings.length === 0 ? (
        <Empty message="No Slack Huddles recorded yet." icon="💬" />
      ) : (
        <div className="slack-meetings-list">
          {meetings.slice(0, 6).map((meeting) => {
            const isActive = meeting.status === "active";
            const processing = meeting.processing_status || "pending";

            return (
              <div className="slack-meeting-row" key={meeting.meeting_id}>
                <div className="slack-status-icon">💬</div>

                <div className="slack-meeting-main">
                  <strong>
                    {meeting.huddle_id
                      ? `Huddle ${meeting.huddle_id}`
                      : "Slack Huddle"}
                  </strong>
                  <span className="meta">
                    {timeAgo(meeting.started_at) || "Time unknown"}
                    {" · "}
                    {(meeting.participants || []).length} participant
                    {(meeting.participants || []).length === 1 ? "" : "s"}
                    {" · "}
                    {formatHuddleDuration(meeting.duration_seconds)}
                  </span>
                </div>

                <span
                  className={`slack-live-dot ${isActive ? "online" : "offline"}`}
                  title={isActive ? "Huddle active" : "Huddle ended"}
                />

                <span
                  className={`status-pill ${
                    processing === "completed"
                      ? "status-completed"
                      : processing === "processing"
                      ? "status-progress"
                      : processing === "failed"
                      ? "status-overdue"
                      : "status-pending"
                  }`}
                >
                  {processing === "completed"
                    ? "Processed"
                    : processing === "processing"
                    ? "Processing…"
                    : processing === "failed"
                    ? "Failed"
                    : isActive
                    ? "In Progress"
                    : "Pending"}
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

/* =========================================================
   SLACK MEETINGS PAGE
========================================================= */

function SlackMeetingsPage() {
  const [meetings, setMeetings] = useState([]);
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState(null);
  const [details, setDetails] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadMeetings() {
    try {
      setLoading(true);
      setError("");
      const data = await getSlackMeetings();
      setMeetings(normalizeMeetings(data));
    } catch (err) {
      setError(getApiError(err, "Could not load Slack meetings."));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    queueMicrotask(loadMeetings);
  }, []);

  async function toggleMeeting(meeting) {
    const id = getMeetingId(meeting);
    if (!id) return;

    if (expanded === id) {
      setExpanded(null);
      return;
    }

    setExpanded(id);
    if (details[id]) return;

    try {
      const data = await getSlackMeeting(id);
      setDetails((current) => ({ ...current, [id]: data }));
    } catch (err) {
      setError(getApiError(err, "Could not load Slack meeting details."));
    }
  }

  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    if (!q) return meetings;

    return meetings.filter((meeting) => {
      const text = [
        meeting?.huddle_id || "",
        meeting?.summary || "",
        meeting?.channel_id || "",
        getMeetingId(meeting),
      ]
        .join(" ")
        .toLowerCase();

      return text.includes(q);
    });
  }, [meetings, query]);

  return (
    <Page
      title="Slack Meetings"
      subtitle="Browse Slack Huddles captured and processed by the assistant."
    >
      <div className="search-toolbar">
        <div className="search-input-wrapper">
          <span>⌕</span>
          <input
            type="text"
            placeholder="Search by huddle ID, channel or summary..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <span className="result-count">{filtered.length} meetings</span>
      </div>

      {loading && <Loading message="Loading Slack meetings..." />}
      {error && <ErrorPanel message={error} onRetry={loadMeetings} />}

      {!loading && !error && filtered.length === 0 && (
        <div className="panel">
          <Empty
            message={
              query
                ? `No Slack meetings found for "${query}".`
                : "No Slack Huddles recorded yet."
            }
            icon="💬"
          />
        </div>
      )}

      {!loading && filtered.length > 0 && (
        <div className="meeting-list">
          {filtered.map((meeting) => {
            const id = getMeetingId(meeting);
            const open = expanded === id;
            const detail = details[id] || meeting;
            const isActive = meeting.status === "active";
            const processing = meeting.processing_status || "pending";
            const participantCount = (meeting.participants || []).length;

            return (
              <div
                className={`panel meeting-card ${open ? "meeting-open" : ""}`}
                key={id}
              >
                <button
                  type="button"
                  className="meeting-header-button"
                  onClick={() => toggleMeeting(meeting)}
                >
                  <span className="expand-icon">{open ? "▼" : "▶"}</span>

                  <div className="slack-status-icon">💬</div>

                  <div className="meeting-title-block">
                    <strong>
                      {meeting.huddle_id
                        ? `Huddle ${meeting.huddle_id}`
                        : "Slack Huddle"}
                    </strong>
                    <span className="meta">
                      {timeAgo(meeting.started_at) || "Time unknown"}
                      {" · "}
                      {participantCount} participant
                      {participantCount === 1 ? "" : "s"}
                      {" · "}
                      {formatHuddleDuration(meeting.duration_seconds)}
                    </span>
                  </div>

                  <span
                    className={`status-pill ${
                      processing === "completed"
                        ? "status-completed"
                        : processing === "processing"
                        ? "status-progress"
                        : processing === "failed"
                        ? "status-overdue"
                        : "status-pending"
                    }`}
                  >
                    {processing === "completed"
                      ? "Processed"
                      : processing === "processing"
                      ? "Processing…"
                      : processing === "failed"
                      ? "Failed"
                      : isActive
                      ? "In Progress"
                      : "Pending"}
                  </span>
                </button>

                {open && <MeetingDetails meeting={detail} />}
              </div>
            );
          })}
        </div>
      )}
    </Page>
  );
}

/* =========================================================
   DASHBOARD
========================================================= */
 
function Dashboard({ pushToast }) {
  const [meetings, setMeetings] = useState([]);
  const [actionItems, setActionItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
 
  async function loadDashboard() {
    try {
      setLoading(true);
      setError("");
 
      const [meetingData, actionData] = await Promise.all([
        getMeetings(),
        getActionItems(),
      ]);
 
      setMeetings(normalizeMeetings(meetingData));
      setActionItems(normalizeActionItems(actionData));
    } catch (err) {
      console.error("Dashboard error:", err);
      setError(getApiError(err, "Could not load dashboard."));
    } finally {
      setLoading(false);
    }
  }
 
  useEffect(() => {
    queueMicrotask(loadDashboard);
  }, []);
 
  const pending = actionItems.filter((item) => item.status === "pending").length;
  const completed = actionItems.filter((item) => item.status === "completed").length;
  const overdue = actionItems.filter((item) => isOverdue(item)).length;
  const completionRate = actionItems.length
    ? Math.round((completed / actionItems.length) * 100)
    : 0;
 
  if (loading) {
    return (
      <Page title="Dashboard" subtitle="Overview of your meeting intelligence.">
        <Loading message="Loading dashboard..." />
      </Page>
    );
  }
 
  if (error) {
    return (
      <Page title="Dashboard">
        <ErrorPanel message={error} onRetry={loadDashboard} />
      </Page>
    );
  }
 
  return (
    <Page
      title="Dashboard"
      subtitle="Overview of your meeting intelligence."
      actions={
        <button className="secondary-button" onClick={loadDashboard}>
          ↻ Refresh
        </button>
      }
    >
      <UploadPanel onUploaded={loadDashboard} pushToast={pushToast} />
 
      <SlackMeetings />
 
      <div className="stats-grid">
        <StatCard label="Total Meetings" value={meetings.length} icon="◫" />
        <StatCard label="Action Items" value={actionItems.length} icon="✓" />
        <StatCard label="Pending" value={pending} tone="amber" icon="◷" />
        <StatCard label="Overdue" value={overdue} tone="brick" icon="!" />
      </div>
 
      <div className="dashboard-grid">
        <div className="panel">
          <div className="panel-header">
            <h2>Recent Meetings</h2>
            <Link to="/meetings">View all →</Link>
          </div>
 
          {meetings.length === 0 ? (
            <Empty message="No meetings found. Upload your first recording." />
          ) : (
            <div className="meeting-list">
              {meetings.slice(0, 5).map((meeting) => (
                <MeetingPreview key={getMeetingId(meeting)} meeting={meeting} />
              ))}
            </div>
          )}
        </div>
 
        <div className="panel completion-panel">
          <div className="panel-header">
            <h2>Completion Rate</h2>
          </div>
 
          <div className="completion-ring-wrap">
            <svg viewBox="0 0 120 120" className="completion-ring">
              <circle cx="60" cy="60" r="52" className="ring-track" />
              <circle
                cx="60"
                cy="60"
                r="52"
                className="ring-progress"
                style={{
                  strokeDasharray: `${2 * Math.PI * 52}`,
                  strokeDashoffset: `${
                    2 * Math.PI * 52 * (1 - completionRate / 100)
                  }`,
                }}
              />
            </svg>
            <div className="completion-ring-label">
              <strong>{completionRate}%</strong>
              <span>done</span>
            </div>
          </div>
 
          <div className="quick-actions">
            <Link to="/meetings">
              <span>◫</span>
              View Meetings
            </Link>
            <Link to="/action-items">
              <span>✓</span>
              Action Items
            </Link>
            <Link to="/ask">
              <span>✦</span>
              Ask AI
            </Link>
            <Link to="/search">
              <span>⌕</span>
              Semantic Search
            </Link>
          </div>
        </div>
      </div>
 
      <div className="panel">
        <div className="panel-header">
          <h2>Action Item Summary</h2>
        </div>
 
        <div className="summary-grid">
          <div>
            <span>Pending</span>
            <strong>{pending}</strong>
          </div>
          <div>
            <span>Completed</span>
            <strong>{completed}</strong>
          </div>
          <div>
            <span>Overdue</span>
            <strong>{overdue}</strong>
          </div>
        </div>
      </div>
    </Page>
  );
}
 
/* =========================================================
   MEETING PREVIEW
========================================================= */
 
function MeetingPreview({ meeting }) {
  const id = getMeetingId(meeting);
 
  return (
    <div className="meeting-preview">
      <div className="meeting-avatar">{initials(getMeetingTitle(meeting))}</div>
 
      <div className="meeting-preview-main">
        <strong>{getMeetingTitle(meeting)}</strong>
        <span className="meta">{timeAgo(meeting?.uploaded_at)}</span>
      </div>
 
      <div className="preview-right">
        <span className="badge processed">Processed</span>
        <span className="short-id">{id ? id.slice(-8) : "—"}</span>
      </div>
    </div>
  );
}
 
/* =========================================================
   MEETINGS
========================================================= */
 
function Meetings() {
  const [meetings, setMeetings] = useState([]);
  const [query, setQuery] = useState("");
  const [expanded, setExpanded] = useState(null);
  const [details, setDetails] = useState({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
 
  async function loadMeetings() {
    try {
      setLoading(true);
      setError("");
      const data = await getMeetings();
      setMeetings(normalizeMeetings(data));
    } catch (err) {
      setError(getApiError(err, "Could not load meetings."));
    } finally {
      setLoading(false);
    }
  }
 
  useEffect(() => {
    queueMicrotask(loadMeetings);
  }, []);
 
  async function toggleMeeting(meeting) {
    const id = getMeetingId(meeting);
    if (!id) return;
 
    if (expanded === id) {
      setExpanded(null);
      return;
    }
 
    setExpanded(id);
    if (details[id]) return;
 
    try {
      const data = await getMeeting(id);
      setDetails((current) => ({ ...current, [id]: data }));
    } catch (err) {
      setError(getApiError(err, "Could not load meeting details."));
    }
  }
 
  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    if (!q) return meetings;
 
    return meetings.filter((meeting) => {
      const text = [
        getMeetingTitle(meeting),
        meeting?.summary || "",
        meeting?.filename || "",
        getMeetingId(meeting),
      ]
        .join(" ")
        .toLowerCase();
 
      return text.includes(q);
    });
  }, [meetings, query]);
 
  return (
    <Page
      title="Meetings"
      subtitle="Browse, search and analyze your recorded meetings."
      actions={
        <Link className="primary-button" to="/">
          + Upload Meeting
        </Link>
      }
    >
      <div className="search-toolbar">
        <div className="search-input-wrapper">
          <span>⌕</span>
          <input
            type="text"
            placeholder="Search by title, filename or meeting ID..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <span className="result-count">{filtered.length} meetings</span>
      </div>
 
      {loading && <Loading message="Loading meetings..." />}
      {error && <ErrorPanel message={error} onRetry={loadMeetings} />}
 
      {!loading && !error && filtered.length === 0 && (
        <div className="panel">
          <Empty
            message={
              query
                ? `No meetings found for "${query}".`
                : "No meetings found. Upload your first recording."
            }
          />
        </div>
      )}
 
      {!loading && filtered.length > 0 && (
        <div className="meeting-list">
          {filtered.map((meeting) => {
            const id = getMeetingId(meeting);
            const open = expanded === id;
            const detail = details[id] || meeting;
 
            return (
              <div
                className={`panel meeting-card ${open ? "meeting-open" : ""}`}
                key={id}
              >
                <button
                  type="button"
                  className="meeting-header-button"
                  onClick={() => toggleMeeting(meeting)}
                >
                  <span className="expand-icon">{open ? "▼" : "▶"}</span>
 
                  <div className="meeting-avatar">
                    {initials(getMeetingTitle(meeting))}
                  </div>
 
                  <div className="meeting-title-block">
                    <strong>{getMeetingTitle(meeting)}</strong>
                    <span className="meta">
                      {formatDate(meeting?.uploaded_at)}
                      {" · "}
                      {Array.isArray(meeting?.action_items)
                        ? meeting.action_items.length
                        : 0}{" "}
                      action items
                    </span>
                  </div>
 
                  <span className="badge processed">Processed</span>
                </button>
 
                {open && <MeetingDetails meeting={detail} />}
              </div>
            );
          })}
        </div>
      )}
    </Page>
  );
}
 
/* =========================================================
   MEETING DETAILS
========================================================= */
 
function MeetingDetails({ meeting }) {
  const topics = Array.isArray(meeting?.topics) ? meeting.topics : [];
  const decisions = Array.isArray(meeting?.decisions) ? meeting.decisions : [];
  const keyPoints = Array.isArray(meeting?.key_points) ? meeting.key_points : [];
  const questions = Array.isArray(meeting?.open_questions)
    ? meeting.open_questions
    : [];
  const actions = Array.isArray(meeting?.action_items) ? meeting.action_items : [];
 
  return (
    <div className="meeting-details">
      <div className="id-box">
        <span>Meeting ID</span>
        <code>{getMeetingId(meeting) || "Not available"}</code>
      </div>
 
      <DetailSection title="Summary" visible={Boolean(meeting?.summary)}>
        <p>{meeting?.summary || "No summary available."}</p>
      </DetailSection>
 
      <DetailList title="Topics" items={topics} chips />
      <DetailList title="Key Points" items={keyPoints} />
      <DetailList title="Decisions" items={decisions} />
 
      {actions.length > 0 && (
        <section className="detail-section">
          <h4>Action Items</h4>
          <div className="detail-action-list">
            {actions.map((action, index) => (
              <div className="detail-action" key={index}>
                <strong>{action?.task || "Task not specified"}</strong>
                <span>Owner: {action?.owner || "Not specified"}</span>
                <span>Due: {action?.due_date || "Not specified"}</span>
                <span
                  className={`inline-status inline-status-${
                    action?.status || "pending"
                  }`}
                >
                  {action?.status || "pending"}
                </span>
              </div>
            ))}
          </div>
        </section>
      )}
 
      <DetailList title="Open Questions" items={questions} />
 
      {meeting?.transcript && (
        <details className="transcript-box">
          <summary>View transcript</summary>
          <pre>{meeting.transcript}</pre>
        </details>
      )}
    </div>
  );
}
 
function DetailSection({ title, visible, children }) {
  if (!visible) return null;
 
  return (
    <section className="detail-section">
      <h4>{title}</h4>
      {children}
    </section>
  );
}
 
function DetailList({ title, items, chips = false }) {
  if (!items?.length) return null;
 
  const render = (item) =>
    typeof item === "string" ? item : item?.text || item?.task || JSON.stringify(item);
 
  return (
    <section className="detail-section">
      <h4>{title}</h4>
 
      {chips ? (
        <div className="chip-row">
          {items.map((item, index) => (
            <span className="chip" key={index}>
              {render(item)}
            </span>
          ))}
        </div>
      ) : (
        <ul>
          {items.map((item, index) => (
            <li key={index}>{render(item)}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
 
/* =========================================================
   ACTION ITEMS
========================================================= */
 
function ActionItems({ pushToast }) {
  const [items, setItems] = useState([]);
  const [filter, setFilter] = useState("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [updating, setUpdating] = useState("");
 
  async function loadItems() {
    try {
      setLoading(true);
      setError("");
 
      const data = await getActionItems();
      const normalized = normalizeActionItems(data);
 
      /*
        IMPORTANT:
        We preserve the backend action_index.
      */
      const counters = {};
 
      const prepared = normalized.map((item, arrayIndex) => {
        const meetingId = String(item?.meeting_id || item?.meetingId || "").trim();
 
        if (counters[meetingId] === undefined) counters[meetingId] = 0;
 
        const hasBackendIndex =
          item?.action_index !== undefined && item?.action_index !== null;
 
        let actionIndex;
 
        if (hasBackendIndex) {
          actionIndex = Number(item.action_index);
        } else {
          actionIndex = getActionIndex(item, counters[meetingId]);
        }
 
        counters[meetingId] = Math.max(counters[meetingId], actionIndex + 1);
 
        return {
          ...item,
          meeting_id: meetingId,
          __actionIndex: actionIndex,
          __arrayIndex: arrayIndex,
        };
      });
 
      setItems(prepared);
    } catch (err) {
      console.error("Action item loading failed:", err);
      setError(getApiError(err, "Could not load action items."));
    } finally {
      setLoading(false);
    }
  }
 
  useEffect(() => {
    queueMicrotask(loadItems);
  }, []);
 
  const counts = useMemo(() => {
    return {
      all: items.length,
      pending: items.filter((item) => item.status === "pending").length,
      in_progress: items.filter((item) => item.status === "in_progress").length,
      completed: items.filter((item) => item.status === "completed").length,
      overdue: items.filter((item) => isOverdue(item)).length,
    };
  }, [items]);
 
  const visible = useMemo(() => {
    return items.filter((item) => {
      if (filter === "pending") return item.status === "pending" && !isOverdue(item);
      if (filter === "in_progress") return item.status === "in_progress";
      if (filter === "completed") return item.status === "completed";
      if (filter === "overdue") return isOverdue(item);
      return true;
    });
  }, [items, filter]);
 
  async function toggleItem(item) {
    const meetingId = String(item?.meeting_id || item?.meetingId || "").trim();
    const actionId = String(item?.action_id || item?.actionId || "").trim();

    if (!meetingId) {
      setError("This action item has no meeting ID.");
      return;
    }

    if (!actionId) {
      setError("This action item has no action ID.");
      return;
    }

    /*
      Checkbox is deliberately two-state:
      pending → completed
      completed → pending
      If the item is in_progress, clicking checkbox will mark it completed.
    */
    const oldStatus = item.status || "pending";
    const newStatus = oldStatus === "completed" ? "pending" : "completed";
    const key = `${meetingId}-${actionId}`;

    if (updating === key) return;

    setUpdating(key);
    setError("");

    console.log("Checkbox clicked:", { meetingId, actionId, oldStatus, newStatus });

    try {
      /*
        IMPORTANT:
        Backend is called FIRST. React state changes only after
        the PATCH returns successfully.
      */
      const response = await updateActionItem(meetingId, actionId, newStatus);
      console.log("PATCH successful:", response);

      setItems((currentItems) =>
        currentItems.map((currentItem) => {
          const currentMeetingId = String(
            currentItem?.meeting_id || currentItem?.meetingId || ""
          ).trim();

          const currentActionId = String(
            currentItem?.action_id || currentItem?.actionId || ""
          ).trim();

          if (currentMeetingId === meetingId && currentActionId === actionId) {
            return { ...currentItem, status: newStatus };
          }

          return currentItem;
        })
      );
 
      pushToast?.(
        newStatus === "completed" ? "Marked complete" : "Reopened",
        "success"
      );
    } catch (err) {
      console.error("PATCH action item failed:", err);
      const msg = getApiError(err, "Could not update action item.");
      setError(msg);
      pushToast?.(msg, "error");
    } finally {
      setUpdating("");
    }
  }
 
  if (loading) {
    return (
      <Page
        title="Action Items"
        subtitle="Track responsibilities, status and deadlines."
      >
        <Loading message="Loading action items..." />
      </Page>
    );
  }
 
  return (
    <Page
      title="Action Items"
      subtitle="Track responsibilities, status and deadlines."
      actions={
        <button className="secondary-button" onClick={loadItems}>
          ↻ Refresh
        </button>
      }
    >
      {error && <ErrorPanel message={error} onRetry={loadItems} />}
 
      <div className="tabs">
        {["all", "pending", "in_progress", "completed", "overdue"].map((name) => (
          <button
            type="button"
            key={name}
            className={filter === name ? "tab active" : "tab"}
            onClick={() => setFilter(name)}
          >
            {name === "in_progress"
              ? "In Progress"
              : name.charAt(0).toUpperCase() + name.slice(1)}
            <span>{counts[name]}</span>
          </button>
        ))}
      </div>
 
      <div className="panel">
        {visible.length === 0 ? (
          <Empty message="No action items in this category." />
        ) : (
          <div className="action-list">
            {visible.map((item, index) => {
              const meetingId = String(
                item?.meeting_id || item?.meetingId || ""
              ).trim();
 
              const actionId = String(
                item?.action_id || item?.actionId || `idx-${index}`
              ).trim();

              const key = `${meetingId}-${actionId}`;
              const completed = item.status === "completed";
              const inProgress = item.status === "in_progress";
              const overdue = isOverdue(item);
              const isUpdating = updating === key;
 
              return (
                <div
                  className={`action-row ${completed ? "done" : ""} ${
                    overdue ? "overdue" : ""
                  } ${inProgress ? "in-progress" : ""}`}
                  key={key}
                >
                  <label className={`checkbox-wrap ${isUpdating ? "updating" : ""}`}>
                    <input
                      type="checkbox"
                      checked={completed}
                      disabled={isUpdating}
                      onChange={() => toggleItem(item)}
                    />
                    <span className="custom-checkbox">
                      {isUpdating ? "…" : completed ? "✓" : ""}
                    </span>
                  </label>
 
                  <div className="action-main">
                    <strong className="action-text">
                      {item?.task || "Task not specified"}
                    </strong>
 
                    <span className="action-meta">
                      {item?.meeting_title || "Unknown meeting"}
                      {" · "}
                      {item?.owner || "Not specified"}
                      {" · due "}
                      {item?.due_date || "Not specified"}
                    </span>
 
                    <small className="action-index">
                      Action #{item?.action_index ?? item?.__actionIndex ?? index}
                    </small>
                  </div>
 
                  <span
                    className={`status-pill ${
                      completed
                        ? "status-completed"
                        : inProgress
                        ? "status-progress"
                        : overdue
                        ? "status-overdue"
                        : "status-pending"
                    }`}
                  >
                    {completed
                      ? "Completed"
                      : inProgress
                      ? "In Progress"
                      : overdue
                      ? "Overdue"
                      : "Pending"}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </Page>
  );
}
 
/* =========================================================
   ASK AI
========================================================= */
 
const SUGGESTED_PROMPTS = [
  "What decisions were made this week?",
  "List all open action items for me",
  "Summarize the last meeting",
];
 
function AskAI() {
  const [messages, setMessages] = useState([
    {
      id: "welcome",
      role: "ai",
      text:
        "Ask me anything about your stored meetings. I can answer questions using the meeting knowledge base.",
    },
  ]);
 
  const [question, setQuestion] = useState("");
  const [thinking, setThinking] = useState(false);
  const chatEndRef = useRef(null);
 
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, thinking]);
 
  async function ask(overrideText) {
    const q = (overrideText ?? question).trim();
    if (!q || thinking) return;
 
    const userMessage = { id: `user-${crypto.randomUUID()}`, role: "user", text: q };
 
    /* Functional update prevents old messages from being lost. */
    setMessages((current) => [...current, userMessage]);
    setQuestion("");
    setThinking(true);
 
    try {
      const data = await askQuestion(q);
      const answer = getAnswer(data);
 
      setMessages((current) => [
        ...current,
        { id: `ai-${crypto.randomUUID()}`, role: "ai", text: answer },
      ]);
    } catch (err) {
      const message = getApiError(err, "Could not reach the AI backend.");
 
      setMessages((current) => [
        ...current,
        { id: `error-${crypto.randomUUID()}`, role: "ai", text: `Something went wrong: ${message}` },
      ]);
    } finally {
      setThinking(false);
    }
  }
 
  function handleKeyDown(event) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      ask();
    }
  }
 
  function clearChat() {
    setMessages([
      {
        id: `welcome-${Date.now()}`,
        role: "ai",
        text: "Chat cleared. Ask me anything about your stored meetings.",
      },
    ]);
  }
 
  const showSuggestions = messages.length === 1;
 
  return (
    <Page
      title="Ask AI"
      subtitle="Ask questions about your meeting knowledge base."
      actions={
        <button className="secondary-button" onClick={clearChat}>
          Clear Chat
        </button>
      }
    >
      <div className="panel ask-panel">
        <div className="chat-area">
          {messages.map((message) => (
            <div key={message.id} className={`chat-message ${message.role}`}>
              <div className="chat-avatar">
                {message.role === "user" ? "You" : <Waveform bars={3} size="xs" tone="violet" />}
              </div>
 
              <div className="chat-bubble">{message.text}</div>
            </div>
          ))}
 
          {thinking && (
            <div className="chat-message ai">
              <div className="chat-avatar">
                <Waveform bars={3} size="xs" tone="violet" active />
              </div>
              <div className="chat-bubble thinking">
                <Waveform bars={10} active tone="violet" size="xs" />
              </div>
            </div>
          )}
 
          {showSuggestions && (
            <div className="suggestion-row">
              {SUGGESTED_PROMPTS.map((prompt) => (
                <button
                  type="button"
                  key={prompt}
                  className="suggestion-chip"
                  onClick={() => ask(prompt)}
                >
                  {prompt}
                </button>
              ))}
            </div>
          )}
 
          <div ref={chatEndRef} />
        </div>
 
        <div className="ask-box">
          <input
            type="text"
            placeholder="Ask something about your meetings..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={thinking}
          />
 
          <button
            type="button"
            onClick={() => ask()}
            disabled={!question.trim() || thinking}
          >
            {thinking ? "Thinking..." : "Ask AI"}
          </button>
        </div>
      </div>
    </Page>
  );
}
 
/* =========================================================
   SEMANTIC SEARCH
========================================================= */
 
function Search() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [searched, setSearched] = useState(false);
  const timerRef = useRef(null);
 
  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);
 
  function handleSearch(value) {
    setQuery(value);
    setError("");
 
    if (timerRef.current) clearTimeout(timerRef.current);
 
    const q = value.trim();
    if (!q) {
      setResults([]);
      setSearched(false);
      return;
    }
 
    timerRef.current = setTimeout(() => {
      performSearch(q);
    }, 500);
  }
 
  async function performSearch(q) {
    try {
      setLoading(true);
      setError("");
      setSearched(true);
 
      const data = await searchMeetings(q);
      setResults(normalizeSearchResults(data));
    } catch (err) {
      setError(getApiError(err, "Semantic search failed."));
      setResults([]);
    } finally {
      setLoading(false);
    }
  }
 
  return (
    <Page
      title="Semantic Search"
      subtitle="Search your meeting knowledge base using meaning, not just keywords."
    >
      <div className="semantic-search-hero">
        <Waveform bars={30} active tone="teal" size="md" />
        <div>
          <h2>Search your meetings</h2>
          <p>
            Ask naturally about previous discussions, decisions, clients,
            pricing, tasks or topics.
          </p>
        </div>
      </div>
 
      <div className="semantic-input">
        <span>⌕</span>
        <input
          type="text"
          placeholder="Example: What did we decide about the frontend?"
          value={query}
          onChange={(e) => handleSearch(e.target.value)}
        />
        {loading && <span className="small-spinner" />}
      </div>
 
      {error && <ErrorPanel message={error} />}
 
      {!loading && !query && !searched && (
        <div className="panel">
          <Empty message="Start typing to search across your meetings." icon="⌕" />
        </div>
      )}
 
      {!loading && searched && !error && results.length === 0 && (
        <div className="panel">
          <Empty message={`No semantic results found for "${query}".`} />
        </div>
      )}
 
      {results.length > 0 && (
        <div className="search-results">
          {results.map((result, index) => {
            const id = getMeetingId(result);
 
            return (
              <div className="panel search-result" key={id || index}>
                <div className="search-result-head">
                  <div>
                    <h3>{getMeetingTitle(result)}</h3>
                    <span className="meta">{formatDate(result?.uploaded_at)}</span>
                  </div>
 
                  {id && <code className="result-id">{id}</code>}
                </div>
 
                <p>
                  {result?.summary ||
                    result?.text ||
                    result?.content ||
                    "Relevant meeting found."}
                </p>
 
                {result?.score !== undefined && (
                  <div className="score-bar-wrap">
                    <div className="score-bar">
                      <div
                        className="score-bar-fill"
                        style={{ width: `${Math.min(Number(result.score) * 100, 100)}%` }}
                      />
                    </div>
                    <span className="score">
                      Relevance: {Number(result.score).toFixed(3)}
                    </span>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </Page>
  );
}
 
/* =========================================================
   APP
========================================================= */
 
function App() {
  const { toasts, push, dismiss } = useToasts();
 
  return (
    <BrowserRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard pushToast={push} />} />
          <Route path="/meetings" element={<Meetings />} />
          <Route path="/slack-meetings" element={<SlackMeetingsPage />} />
          <Route path="/action-items" element={<ActionItems pushToast={push} />} />
          <Route path="/ask" element={<AskAI />} />
          <Route path="/search" element={<Search />} />
        </Routes>
      </Layout>
 
      <ToastStack toasts={toasts} onDismiss={dismiss} />
    </BrowserRouter>
  );
}
 
export default App;
 
