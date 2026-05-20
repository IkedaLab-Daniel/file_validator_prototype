"use client";

import { useCallback, useEffect, useState } from "react";

type DocumentType = "GOV_ID" | "RESIDENCY" | "RESUME";

type UploadRecord = {
  id: number;
  document_type: DocumentType;
  file_url: string | null;
  original_name: string;
  content_type: string;
  size_bytes: number;
  checksum_sha256: string;
  scan_status: string;
  ai_reason: string;
  ai_model: string;
  ai_checked_at: string | null;
  ai_last_error: string;
  created_at: string;
  updated_at: string;
};

const API_BASE =
  process.env.NEXT_PUBLIC_API_BASE ?? "http://127.0.0.1:8000";
const MAX_SIZE_MB = 10;
const MAX_SIZE_BYTES = MAX_SIZE_MB * 1024 * 1024;

const DOCUMENTS: Array<{
  type: DocumentType;
  label: string;
  helper: string;
  accepts: string;
  description: string;
}> = [
  {
    type: "GOV_ID",
    label: "Government ID",
    helper: "PDF or JPG/PNG",
    accepts: ".pdf,.jpg,.jpeg,.png",
    description: "Passport, national ID, or driver license scan.",
  },
  {
    type: "RESIDENCY",
    label: "Proof of Residency",
    helper: "PDF or JPG/PNG",
    accepts: ".pdf,.jpg,.jpeg,.png",
    description: "Utility bill, bank statement, or lease agreement.",
  },
  {
    type: "RESUME",
    label: "Resume",
    helper: "PDF only",
    accepts: ".pdf",
    description: "One concise, current resume in PDF format.",
  },
];

const EMPTY_UPLOADS: Record<DocumentType, UploadRecord | null> = {
  GOV_ID: null,
  RESIDENCY: null,
  RESUME: null,
};

const EMPTY_UPLOAD_ERRORS: Record<DocumentType, string | null> = {
  GOV_ID: null,
  RESIDENCY: null,
  RESUME: null,
};

const EMPTY_UPLOADING: Record<DocumentType, boolean> = {
  GOV_ID: false,
  RESIDENCY: false,
  RESUME: false,
};

const statusStyles: Record<string, string> = {
  pending: "border-amber-200 bg-amber-100 text-amber-900",
  clean: "border-emerald-200 bg-emerald-100 text-emerald-900",
  rejected: "border-rose-200 bg-rose-100 text-rose-900",
  failed: "border-slate-200 bg-slate-100 text-slate-700",
  missing: "border-slate-200 bg-slate-100 text-slate-700",
};

const extractErrorMessage = (payload: unknown, fallback: string) => {
  if (!payload || typeof payload !== "object") {
    return fallback;
  }

  const data = payload as Record<string, unknown>;
  if (typeof data.detail === "string") {
    return data.detail;
  }

  const messages: string[] = [];
  for (const value of Object.values(data)) {
    if (Array.isArray(value)) {
      for (const entry of value) {
        if (typeof entry === "string") {
          messages.push(entry);
        }
      }
    } else if (typeof value === "string") {
      messages.push(value);
    }
  }

  return messages.length ? messages.join(" ") : fallback;
};

const formatBytes = (bytes: number) => {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const exponent = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
  const value = (bytes / 1024 ** exponent).toFixed(exponent ? 1 : 0);
  return `${value} ${units[exponent]}`;
};

const formatDateTime = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString();
};

const getStoredValue = (key: string) => {
  if (typeof window === "undefined") {
    return null;
  }
  return localStorage.getItem(key);
};

export default function Home() {
  const [accessToken, setAccessToken] = useState<string | null>(() =>
    getStoredValue("fv_access_token")
  );
  const [activeUser, setActiveUser] = useState<string | null>(() =>
    getStoredValue("fv_username")
  );
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [uploads, setUploads] = useState<Record<DocumentType, UploadRecord | null>>(
    EMPTY_UPLOADS
  );
  const [uploading, setUploading] = useState<Record<DocumentType, boolean>>(
    EMPTY_UPLOADING
  );
  const [uploadErrors, setUploadErrors] = useState<Record<DocumentType, string | null>>(
    EMPTY_UPLOAD_ERRORS
  );

  const handleLogout = useCallback(() => {
    setAccessToken(null);
    setActiveUser(null);
    setUploads(EMPTY_UPLOADS);
    localStorage.removeItem("fv_access_token");
    localStorage.removeItem("fv_refresh_token");
    localStorage.removeItem("fv_username");
  }, []);

  const fetchUploads = useCallback(async (token: string) => {
    try {
      const response = await fetch(`${API_BASE}/api/uploads/`, {
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        if (response.status === 401) {
          handleLogout();
        }
        return;
      }

      const data = (await response.json()) as UploadRecord[];
      const nextUploads: Record<DocumentType, UploadRecord | null> = {
        GOV_ID: null,
        RESIDENCY: null,
        RESUME: null,
      };

      for (const entry of data) {
        nextUploads[entry.document_type] = entry;
      }

      setUploads(nextUploads);
    } catch (error) {
      console.error(error);
    }
  }, [handleLogout]);

  useEffect(() => {
    if (!accessToken) {
      return undefined;
    }
    const timer = setTimeout(() => {
      void fetchUploads(accessToken);
    }, 0);
    return () => clearTimeout(timer);
  }, [accessToken, fetchUploads]);

  useEffect(() => {
    if (!accessToken) {
      return undefined;
    }

    const hasPending = Object.values(uploads).some(
      (record) => record?.scan_status === "pending"
    );
    if (!hasPending) {
      return undefined;
    }

    const interval = setInterval(() => {
      void fetchUploads(accessToken);
    }, 6000);

    return () => clearInterval(interval);
  }, [accessToken, uploads, fetchUploads]);

  const handleLogin = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoginError(null);
    setStatusMessage(null);

    try {
      const response = await fetch(`${API_BASE}/auth/jwt/create/`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ username, password }),
      });

      if (!response.ok) {
        const errorPayload = await response.json().catch(() => null);
        setLoginError(extractErrorMessage(errorPayload, "Login failed."));
        return;
      }

      const payload = (await response.json()) as {
        access: string;
        refresh: string;
      };

      setAccessToken(payload.access);
      setActiveUser(username);
      localStorage.setItem("fv_access_token", payload.access);
      localStorage.setItem("fv_refresh_token", payload.refresh);
      localStorage.setItem("fv_username", username);
      setPassword("");
      setStatusMessage("Session active. Server-side validation enabled.");
      fetchUploads(payload.access);
    } catch {
      setLoginError("Login failed.");
    }
  };

  const handleUpload = async (documentType: DocumentType, file: File) => {
    if (!accessToken) {
      setUploadErrors((prev) => ({
        ...prev,
        [documentType]: "Sign in to upload files.",
      }));
      return;
    }

    if (file.size > MAX_SIZE_BYTES) {
      setUploadErrors((prev) => ({
        ...prev,
        [documentType]: `File exceeds ${MAX_SIZE_MB} MB limit.`,
      }));
      return;
    }

    setUploadErrors((prev) => ({ ...prev, [documentType]: null }));
    setUploading((prev) => ({ ...prev, [documentType]: true }));

    try {
      const body = new FormData();
      body.append("document_type", documentType);
      body.append("file", file);

      const response = await fetch(`${API_BASE}/api/uploads/`, {
        method: "POST",
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        body,
      });

      if (!response.ok) {
        const errorPayload = await response.json().catch(() => null);
        setUploadErrors((prev) => ({
          ...prev,
          [documentType]: extractErrorMessage(errorPayload, "Upload failed."),
        }));
        return;
      }

      const payload = (await response.json()) as UploadRecord;
      setUploads((prev) => ({ ...prev, [payload.document_type]: payload }));
    } catch {
      setUploadErrors((prev) => ({
        ...prev,
        [documentType]: "Upload failed.",
      }));
    } finally {
      setUploading((prev) => ({ ...prev, [documentType]: false }));
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-background text-foreground">
      <div className="hero-orb hero-orb-top" />
      <div className="hero-orb hero-orb-bottom" />

      <header className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-6 pt-10 lg:flex-row lg:items-center lg:justify-between">
        <div className="space-y-2">
          <p className="text-xs uppercase tracking-[0.24em] text-slate-500">
            Secure file intake
          </p>
          <h1 className="font-serif text-4xl leading-tight sm:text-5xl">
            Trustworthy uploads for sensitive documents.
          </h1>
        </div>
        <div className="flex flex-wrap items-center gap-3 text-xs text-slate-600">
          <span className="rounded-full border border-slate-200 bg-white/80 px-3 py-1">
            JWT required
          </span>
          <span className="rounded-full border border-slate-200 bg-white/80 px-3 py-1">
            Max {MAX_SIZE_MB} MB
          </span>
          <span className="rounded-full border border-slate-200 bg-white/80 px-3 py-1">
            Signature validation
          </span>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl px-6 pb-20 pt-10">
        <section className="grid gap-8 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="space-y-6">
            <p className="max-w-xl text-lg text-slate-700">
              Upload Government ID, Proof of Residency, and Resume files with a
              backend that verifies extensions, MIME signatures, size limits,
              and blocks archives. Every file is hashed and queued for a scan
              placeholder so bypass attempts are rejected before storage.
            </p>
            <div className="grid gap-3 sm:grid-cols-2">
              <div className="surface rounded-2xl p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
                  Server checks
                </p>
                <p className="mt-3 text-sm text-slate-700">
                  Content sniffing, extension allowlists, archive blocking.
                </p>
              </div>
              <div className="surface rounded-2xl p-4">
                <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
                  Storage
                </p>
                <p className="mt-3 text-sm text-slate-700">
                  Local MEDIA storage with hashed metadata and audit trail.
                </p>
              </div>
            </div>
          </div>

          <div className="surface rounded-3xl p-6">
            <div className="flex items-center justify-between">
              <h2 className="font-serif text-xl">Session</h2>
              {accessToken ? (
                <button
                  onClick={handleLogout}
                  className="rounded-full border border-slate-300 px-3 py-1 text-xs text-slate-700 transition hover:border-slate-400"
                >
                  Sign out
                </button>
              ) : null}
            </div>

            {accessToken ? (
              <div className="mt-4 space-y-3 text-sm text-slate-700">
                <p className="font-medium text-slate-900">
                  Signed in{activeUser ? ` as ${activeUser}` : ""}.
                </p>
                <p>
                  Upload cards are now active. Keep this tab open while the
                  prototype validates files.
                </p>
                {statusMessage ? (
                  <div className="rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-emerald-900">
                    {statusMessage}
                  </div>
                ) : null}
              </div>
            ) : (
              <form className="mt-4 space-y-4" onSubmit={handleLogin}>
                <div className="space-y-2">
                  <label className="text-xs uppercase tracking-[0.22em] text-slate-500">
                    Username
                  </label>
                  <input
                    value={username}
                    onChange={(event) => setUsername(event.target.value)}
                    className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-slate-400"
                    placeholder="Enter username"
                    autoComplete="username"
                    required
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-xs uppercase tracking-[0.22em] text-slate-500">
                    Password
                  </label>
                  <input
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    className="w-full rounded-2xl border border-slate-200 bg-white px-4 py-3 text-sm outline-none transition focus:border-slate-400"
                    placeholder="Enter password"
                    type="password"
                    autoComplete="current-password"
                    required
                  />
                </div>
                {loginError ? (
                  <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                    {loginError}
                  </div>
                ) : null}
                <button
                  type="submit"
                  className="w-full rounded-2xl bg-slate-900 px-4 py-3 text-sm font-semibold text-white transition hover:bg-slate-800"
                >
                  Start secure session
                </button>
                <p className="text-xs text-slate-500">
                  Need an account? Create a user in Django admin or Djoser.
                </p>
              </form>
            )}
          </div>
        </section>

        <section className="mt-10 grid gap-6 lg:grid-cols-3">
          {DOCUMENTS.map((doc) => {
            const record = uploads[doc.type];
            const statusKey = record?.scan_status ?? "missing";
            const statusClass = statusStyles[statusKey] ?? statusStyles.missing;

            return (
              <div key={doc.type} className="surface flex h-full flex-col rounded-3xl p-6">
                <div className="flex items-center justify-between">
                  <h3 className="font-serif text-2xl">{doc.label}</h3>
                  <span
                    className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.2em] ${statusClass}`}
                  >
                    {statusKey}
                  </span>
                </div>
                <p className="mt-3 text-sm text-slate-600">{doc.description}</p>
                {record?.ai_reason && statusKey === "rejected" ? (
                  <p className="mt-3 text-xs text-rose-700">{record.ai_reason}</p>
                ) : null}
                {record?.ai_last_error && statusKey === "pending" ? (
                  <p className="mt-3 text-xs text-amber-700">
                    Last verification error: {record.ai_last_error}
                  </p>
                ) : null}
                <div className="mt-4 rounded-2xl border border-dashed border-slate-200 bg-white/70 px-4 py-3">
                  <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
                    Allowed
                  </p>
                  <p className="mt-1 text-sm text-slate-700">{doc.helper}</p>
                </div>
                <div className="mt-4 space-y-3">
                  <input
                    type="file"
                    accept={doc.accepts}
                    disabled={!accessToken || uploading[doc.type]}
                    className="w-full text-sm file:mr-4 file:rounded-full file:border-0 file:bg-slate-900 file:px-4 file:py-2 file:text-xs file:font-semibold file:text-white file:transition file:hover:bg-slate-800"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      if (file) {
                        handleUpload(doc.type, file);
                      }
                      event.currentTarget.value = "";
                    }}
                  />
                  {uploading[doc.type] ? (
                    <p className="text-xs text-slate-500">Uploading...</p>
                  ) : null}
                  {uploadErrors[doc.type] ? (
                    <p className="text-xs text-rose-700">{uploadErrors[doc.type]}</p>
                  ) : null}
                </div>
                <div className="mt-6 border-t border-slate-200 pt-4 text-xs text-slate-600">
                  {record ? (
                    <div className="space-y-1">
                      <p className="font-semibold text-slate-800">
                        {record.original_name}
                      </p>
                      <p>{formatBytes(record.size_bytes)}</p>
                      {record.ai_checked_at ? (
                        <p>AI checked {formatDateTime(record.ai_checked_at)}</p>
                      ) : null}
                      <p>Updated {formatDateTime(record.updated_at)}</p>
                    </div>
                  ) : (
                    <p>No file uploaded yet.</p>
                  )}
                </div>
              </div>
            );
          })}
        </section>

        <section className="mt-10 surface rounded-3xl p-6">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <h3 className="font-serif text-2xl">Bypass-resistant checks</h3>
              <p className="mt-2 text-sm text-slate-600">
                The backend rejects mismatched extensions, suspicious archives,
                and unknown signatures. Each upload is hashed for audit and
                queued for a scan placeholder to plug in AI or antivirus later.
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white/70 px-4 py-3 text-xs text-slate-600">
              API base: {API_BASE}
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
