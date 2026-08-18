import axios from "axios";

/* =========================================================
   API CONFIG
========================================================= */

const API_BASE_URL =
  import.meta.env.VITE_API_URL ||
  "http://127.0.0.1:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    Accept: "application/json",
  },
});

/* =========================================================
   ERROR HANDLER
========================================================= */

export function getApiError(
  error,
  fallback = "Something went wrong."
) {
  if (!error) {
    return fallback;
  }

  // Axios response error
  if (error.response) {
    const data = error.response.data;

    if (typeof data === "string") {
      return data;
    }

    if (data?.detail) {
      if (typeof data.detail === "string") {
        return data.detail;
      }

      if (Array.isArray(data.detail)) {
        return data.detail
          .map((item) => {
            if (typeof item === "string") {
              return item;
            }

            return (
              item?.msg ||
              item?.message ||
              JSON.stringify(item)
            );
          })
          .join(", ");
      }

      if (typeof data.detail === "object") {
        return (
          data.detail?.message ||
          data.detail?.msg ||
          JSON.stringify(data.detail)
        );
      }
    }

    if (data?.message) {
      return typeof data.message === "string"
        ? data.message
        : JSON.stringify(data.message);
    }

    if (data?.error) {
      return typeof data.error === "string"
        ? data.error
        : JSON.stringify(data.error);
    }

    return `Request failed with status ${error.response.status}.`;
  }

  // Request was made but no response received
  if (error.request) {
    return "Cannot connect to the backend. Make sure FastAPI is running.";
  }

  // Something else went wrong
  if (error.message) {
    return error.message;
  }

  return fallback;
}

/* =========================================================
   NORMALIZE ID
========================================================= */

function cleanMeetingId(meetingId) {
  return String(meetingId ?? "").trim();
}

/* =========================================================
   MEETINGS
========================================================= */

export async function getMeetings() {
  const response = await api.get("/meetings");

  return response.data;
}

/* =========================================================
   SINGLE MEETING
========================================================= */

export async function getMeeting(meetingId) {
  const cleanId = cleanMeetingId(meetingId);

  if (!cleanId) {
    throw new Error("Meeting ID is required.");
  }

  const response = await api.get(
    `/meetings/${encodeURIComponent(cleanId)}`
  );

  return response.data;
}

/* =========================================================
   ACTION ITEMS
========================================================= */

export async function getActionItems() {
  const response = await api.get("/action-items");

  return response.data;
}

/* =========================================================
   UPDATE ACTION ITEM
========================================================= */

export async function updateActionItem(
  meetingId,
  actionIndex,
  status
) {
  const cleanId = cleanMeetingId(meetingId);
  const cleanIndex = Number(actionIndex);

  const allowedStatuses = [
    "pending",
    "in_progress",
    "completed",
  ];

  if (!cleanId) {
    throw new Error("Meeting ID is missing.");
  }

  if (!Number.isInteger(cleanIndex)) {
    throw new Error("Action index must be an integer.");
  }

  if (!allowedStatuses.includes(status)) {
    throw new Error(
      `Invalid status "${status}". Use pending, in_progress, or completed.`
    );
  }

  console.log("PATCH action item:", {
    meetingId: cleanId,
    actionIndex: cleanIndex,
    status,
  });

  const response = await api.patch(
    `/action-items/${encodeURIComponent(cleanId)}/${cleanIndex}`,
    {
      status,
    }
  );

  return response.data;
}

/* =========================================================
   ASK AI
========================================================= */

export async function askQuestion(question) {
  const cleanQuestion = String(question ?? "").trim();

  if (!cleanQuestion) {
    throw new Error("Question cannot be empty.");
  }

  const response = await api.post("/ask", {
    question: cleanQuestion,
  });

  return response.data;
}

/* =========================================================
   SEMANTIC SEARCH
========================================================= */

export async function searchMeetings(query) {
  const cleanQuery = String(query ?? "").trim();

  if (!cleanQuery) {
    return [];
  }

  const response = await api.get("/search", {
    params: {
      query: cleanQuery,
    },
  });

  return response.data;
}

/* =========================================================
   UPLOAD RECORDING
========================================================= */

export async function uploadRecording(
  file,
  onUploadProgress
) {
  if (!file) {
    throw new Error("Please select an audio file.");
  }

  const formData = new FormData();

  formData.append("file", file);

  const response = await api.post(
    "/upload",
    formData,
    {
      headers: {
        "Content-Type": "multipart/form-data",
      },
      onUploadProgress,
    }
  );

  return response.data;
}

/* =========================================================
   FORMAT DATE
========================================================= */

export function formatDate(value) {
  if (!value) {
    return "Date unavailable";
  }

  const date = new Date(value);

  if (Number.isNaN(date.getTime())) {
    return String(value);
  }

  return date.toLocaleString();
}
/* =========================================================
   ZOOM STATUS
========================================================= */

export async function getZoomStatus() {
  const response = await api.get("/zoom/status");

  return response.data;
}

/* =========================================================
   EXPORT
========================================================= */

export default api;