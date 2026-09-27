import { useCallback, useEffect, useState } from "react";
import { Navigate } from "react-router-dom";

import { api, errorMessage, type WorkerDocument } from "../../api";
import { Check, Cross, Lock, Refresh, ShieldCheck } from "../../components/Icons";
import { useAuth } from "../../lib/auth";

export default function VerificationPending() {
  const { user, refresh } = useAuth();
  const [polling, setPolling] = useState(false);
  const workerId = user?.worker_id ?? null;
  const worker = workerId ? `worker #${workerId}` : "your worker account";

  // Auto-redirect if worker has already been approved by council
  if (user?.worker_status === "active") {
    return <Navigate to="/kaam/home" replace />;
  }

  const [docs, setDocs] = useState<WorkerDocument[]>([]);
  const [loadingDocs, setLoadingDocs] = useState(false);
  const [docType, setDocType] = useState<WorkerDocument["document_type"]>("aadhaar");
  const [fileUrl, setFileUrl] = useState("");
  const [filePreview, setFilePreview] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const loadDocuments = useCallback(async () => {
    if (!workerId) return;
    setLoadingDocs(true);
    try {
      const list = await api.workers.documents.list(workerId);
      setDocs(list);
    } catch (e) {
      console.error(errorMessage(e));
    } finally {
      setLoadingDocs(false);
    }
  }, [workerId]);

  useEffect(() => {
    void loadDocuments();
    // Poll auth status every 5 seconds so when council approves, page automatically unlocks
    const timer = setInterval(() => {
      void refresh();
    }, 5000);
    return () => clearInterval(timer);
  }, [loadDocuments, refresh]);

  const recheck = async () => {
    setPolling(true);
    try {
      await refresh();
      await loadDocuments();
    } catch (e) {
      console.error(errorMessage(e));
    } finally {
      setPolling(false);
    }
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (file.size > 5 * 1024 * 1024) {
      setUploadError("File size must be under 5 MB");
      return;
    }

    const reader = new FileReader();
    reader.onload = () => {
      const res = reader.result as string;
      setFilePreview(res);
      setFileUrl(res);
      setUploadError(null);
    };
    reader.readAsDataURL(file);
  };

  const handleUpload = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!workerId || !fileUrl.trim()) return;

    setUploading(true);
    setUploadError(null);
    try {
      await api.workers.documents.add(workerId, {
        document_type: docType,
        file_url: fileUrl.trim(),
      });
      setFileUrl("");
      setFilePreview(null);
      await loadDocuments();
    } catch (err) {
      setUploadError(errorMessage(err));
    } finally {
      setUploading(false);
    }
  };

  const hasAadhaar = docs.some((d) => d.document_type === "aadhaar");
  const isAadhaarVerified = docs.some((d) => d.document_type === "aadhaar" && d.verified);

  const details = [
    { icon: <ShieldCheck size={20} />, label: user?.name ?? "—", hint: "Name" },
    { icon: <Lock size={20} />, label: user?.phone ?? "—", hint: "Phone number" },
    { icon: <Lock size={20} />, label: user?.worker_id ?? "—", hint: "Worker ID" },
  ];

  return (
    <div className="page wide kaam-page" style={{ maxWidth: 840, margin: "0 auto" }}>
      <header className="stack" style={{ gap: 6, marginBottom: 24 }}>
        <h1>Account under review</h1>
        <div className="sub">
          The Sabha Council is verifying your worker profile. Upload your verification documents below to complete your registration.
        </div>
      </header>

      <div className="sabha-grid" style={{ gap: 20 }}>
        {/* Worker Account Card */}
        <section className="card stack" style={{ gap: 14 }}>
          <h2 style={{ fontSize: 18 }}>Worker Account Details</h2>
          <div className="row" style={{ gap: 16, alignItems: "center" }}>
            <div className="avatar" style={{ width: 56, height: 56, fontSize: 20 }}>
              {(user?.name ?? worker).slice(0, 2).toUpperCase()}
            </div>
            <div className="stack" style={{ gap: 2 }}>
              <div style={{ fontWeight: 700, fontSize: 16 }}>{user?.name}</div>
              <div className="tiny muted">
                Status: {(user?.worker_status as string) === "active" ? "Active (Approved)" : "Pending Verification"}
              </div>
            </div>
          </div>

          <div className="stack" style={{ gap: 8 }}>
            {details.map((d) => (
              <div key={d.hint} className="row between small" style={{ borderBottom: "1px solid var(--line-soft)", paddingBottom: 6 }}>
                <span className="muted">{d.hint}</span>
                <span style={{ fontWeight: 600 }}>{d.label}</span>
              </div>
            ))}
          </div>

          <div className="notice info" style={{ marginTop: 8 }}>
            You’ll be matched with jobs once the council verifies your Aadhaar card and approves your profile.
          </div>

          <div className="row" style={{ gap: 10, marginTop: 8 }}>
            <button type="button" className="btn primary small grow" onClick={recheck} disabled={polling}>
              {polling ? <Refresh size={16} /> : "Re-check status"}
            </button>
            <button type="button" className="btn outline small" onClick={() => void api.auth.logout()}>
              Sign out
            </button>
          </div>
        </section>

        {/* Document Upload & KYC Section */}
        <section className="card stack" style={{ gap: 16 }}>
          <div className="row between" style={{ alignItems: "center" }}>
            <h2 style={{ fontSize: 18 }}>KYC & Verification Documents</h2>
            {isAadhaarVerified ? (
              <span className="pill green">✓ Aadhaar Verified</span>
            ) : hasAadhaar ? (
              <span className="pill amber">⏳ Aadhaar Review Pending</span>
            ) : (
              <span className="pill terracotta">⚠️ Aadhaar Required</span>
            )}
          </div>

          {/* Upload Form */}
          <form className="stack" style={{ gap: 12 }} onSubmit={handleUpload}>
            <div className="stack" style={{ gap: 6 }}>
              <label className="label">Select Document Type</label>
              <select
                className="field"
                value={docType}
                onChange={(e) => setDocType(e.target.value as WorkerDocument["document_type"])}
                style={{ width: "100%", height: 44, padding: "0 12px" }}
              >
                <option value="aadhaar">Aadhaar Card (Required for approval)</option>
                <option value="id_proof">Voter ID / Driving License / Passport</option>
                <option value="insurance">Insurance Document</option>
                <option value="vehicle">Vehicle Registration (RC)</option>
                <option value="other">Skill Certificate / Other Document</option>
              </select>
            </div>

            <div className="stack" style={{ gap: 6 }}>
              <label className="label">Upload Document File or Photo</label>
              <input
                type="file"
                accept="image/*,.pdf"
                onChange={handleFileSelect}
                style={{ fontSize: 14 }}
              />
            </div>

            {filePreview && (
              <div className="stack" style={{ gap: 4, alignItems: "center" }}>
                <span className="tiny muted">Selected Document Preview:</span>
                <img
                  src={filePreview}
                  alt="Preview"
                  style={{ maxHeight: 140, borderRadius: 8, border: "1px solid var(--line)" }}
                />
              </div>
            )}

            <div className="stack" style={{ gap: 6 }}>
              <span className="tiny muted">Or paste image/document URL directly:</span>
              <input
                type="url"
                className="field"
                placeholder="https://..."
                value={fileUrl}
                onChange={(e) => {
                  setFileUrl(e.target.value);
                  setFilePreview(e.target.value.startsWith("http") ? e.target.value : null);
                }}
                style={{ width: "100%", height: 40, padding: "0 12px", fontSize: 13 }}
              />
            </div>

            {uploadError && <div className="notice error">{uploadError}</div>}

            <button
              type="submit"
              className="btn green block"
              disabled={uploading || !fileUrl.trim()}
              style={{ minHeight: 44 }}
            >
              {uploading ? "Uploading document…" : "Submit Document for Verification"}
            </button>
          </form>

          {/* List of Uploaded Documents */}
          <div className="stack" style={{ gap: 10, marginTop: 8 }}>
            <h3 style={{ fontSize: 15, margin: 0 }}>Uploaded Documents ({docs.length})</h3>

            {loadingDocs ? (
              <div className="small muted">Loading documents…</div>
            ) : docs.length === 0 ? (
              <div className="notice info small">
                No documents submitted yet. Please upload your Aadhaar Card above so the council can review your profile.
              </div>
            ) : (
              docs.map((d) => (
                <div key={d.id} className="card soft stack" style={{ gap: 8, padding: 12 }}>
                  <div className="row between" style={{ alignItems: "center" }}>
                    <span style={{ fontWeight: 700, textTransform: "capitalize" }}>
                      📄 {d.document_type.replace("_", " ")}
                    </span>
                    {d.verified ? (
                      <span className="pill green" style={{ gap: 4 }}>
                        <Check size={12} /> Verified
                      </span>
                    ) : d.rejection_reason ? (
                      <span className="pill terracotta" style={{ gap: 4 }}>
                        <Cross size={12} /> Rejected
                      </span>
                    ) : (
                      <span className="pill amber">⏳ Pending Council Review</span>
                    )}
                  </div>

                  {d.rejection_reason && (
                    <div className="small notice error" style={{ padding: "6px 10px" }}>
                      Rejection Reason: {d.rejection_reason}. Please re-upload a clear copy above.
                    </div>
                  )}

                  <div className="row between" style={{ fontSize: 12 }}>
                    <a
                      href={d.file_url}
                      target="_blank"
                      rel="noreferrer"
                      className="link"
                      style={{ textDecoration: "underline" }}
                    >
                      View Uploaded Document ↗
                    </a>
                    {d.uploaded_at && (
                      <span className="muted">{new Date(d.uploaded_at).toLocaleDateString()}</span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  );
}

