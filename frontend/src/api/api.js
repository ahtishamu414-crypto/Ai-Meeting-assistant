import axios from "axios";

const API = axios.create({
  baseURL: "http://127.0.0.1:8000",
  headers: {
    "Content-Type": "application/json",
  },
});

/* =========================================================
   ERROR HELPER
========================================================= */

export function getApiError(error, fallback = "Something went wrong.") {
  const detail = error?.response?.data?.detail;

  if (typeof detail === "string") {
    return detail;
  }

  if (detail && typeof detail === "object") {
    return (
      detail.message ||
      detail.error ||
      JSON.stringify(detail)
    );
  }

  if (typeof error?.response?.data === "string") {
    return error.response.data;
  }

  if (error?.message) {
    return error.message;
  }

  return fallback;
}

/* =========================================================
   MEETINGS
========================================================= */

export const getMeetings = async () => {
  const response = await API.get("/meetings");
  return response.data;
};

/* =========================================================
   ACTION ITEMS
========================================================= */

export const getActionItems = async () => {
  const response = await API.get("/action-items");
  return response.data;
};

export const updateActionItem = async (
  meetingId,
  actionIndex,
  status
) => {
  const response = await API.patch(
    `/action-items/${meetingId}/${actionIndex}`,
    {
      status: status,
    }
  );

  return response.data;
};

export const askQuestion = async (question) => {
  const response = await API.post("/ask", { question });
  return response.data;
};

/* =========================================================
   UPLOAD MEETING
========================================================= */

export const uploadMeeting = async (file) => {
  const formData = new FormData();

  formData.append("file", file);

  const response = await API.post("/upload", formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });

  return response.data;
};

export default API;
