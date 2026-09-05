/**
 * Admin Dashboard page (Redesigned - Pass 2).
 * 
 * Data-dense screen for reviewing system performance.
 * Uses the app's color tokens for charts, clear hierarchy for metrics.
 */
import { useState, useEffect } from "react";
import { useAuth } from "../context/AuthContext";
import { fetchLatestEval, fetchEvalList } from "../api/chatApi";
import EvalCharts from "../components/EvalCharts";

export default function AdminDashboard() {
  const { user } = useAuth();
  const [evalReport, setEvalReport] = useState(null);
  const [evalList, setEvalList] = useState([]);
  const [selectedReport, setSelectedReport] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Load latest eval report on mount
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const [latestRes, listRes] = await Promise.all([
          fetchLatestEval(),
          fetchEvalList(),
        ]);
        
        if (latestRes.report) {
          setEvalReport(latestRes.report);
          setSelectedReport(latestRes.filename);
        }
        
        if (listRes.reports) {
          setEvalList(listRes.reports);
        }
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    
    loadData();
  }, []);

  const handleReportSelect = async (filename) => {
    try {
      setLoading(true);
      const res = await fetch(`/api/eval/${filename}`);
      const data = await res.json();
      if (data.report) {
        setEvalReport(data.report);
        setSelectedReport(filename);
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "300px" }}>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "var(--space-4)", color: "var(--ink-muted)" }}>
          <div style={{ width: "var(--space-8)", height: "var(--space-8)", border: "3px solid var(--border)", borderTopColor: "var(--accent)", borderRadius: "var(--radius-full)", animation: `spin var(--spin-duration) linear infinite` }} />
          <span style={{ fontSize: "var(--text-md)" }}>Loading evaluation data…</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ padding: "var(--space-8)", textAlign: "center" }}>
        <div style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: "var(--space-12)", height: "var(--space-12)", borderRadius: "var(--radius-full)", background: "var(--trust-low-bg)", color: "var(--trust-low)", marginBottom: "var(--space-4)" }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
        </div>
        <h2 style={{ margin: "0 0 var(--space-2)", fontSize: "var(--text-xl)", fontWeight: "var(--font-semibold)", color: "var(--ink)" }}>Error Loading Dashboard</h2>
        <p style={{ margin: 0, color: "var(--ink-muted)" }}>{error}</p>
      </div>
    );
  }

  if (!evalReport) {
    return (
      <div style={{ padding: "var(--space-8)", textAlign: "center" }}>
        <div style={{ display: "inline-flex", alignItems: "center", justifyContent: "center", width: "var(--space-12)", height: "var(--space-12)", borderRadius: "var(--radius-full)", background: "var(--accent-subtle)", color: "var(--accent)", marginBottom: "var(--space-4)" }}>
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="16" y1="13" x2="8" y2="13" />
            <line x1="16" y1="17" x2="8" y2="17" />
            <polyline points="10 9 9 9 8 9" />
          </svg>
        </div>
        <h2 style={{ margin: "0 0 var(--space-2)", fontSize: "var(--text-xl)", fontWeight: "var(--font-semibold)", color: "var(--ink)" }}>No Evaluation Data</h2>
        <p style={{ margin: "0 0 var(--space-6)", color: "var(--ink-muted)" }}>Run the evaluation harness first:</p>
        <pre style={{ textAlign: "left", background: "var(--paper)", border: "1px solid var(--border)", padding: "var(--space-4)", borderRadius: "var(--radius-md)", fontSize: "var(--text-sm)", fontFamily: "var(--font-mono)", overflow: "auto" }}>
          cd ai-service/eval && python run_eval.py
        </pre>
      </div>
    );
  }

  const summary = evalReport.summary || {};
  const byCategory = evalReport.by_category || {};
  const metadata = evalReport.metadata || {};

  // Metric card component
  const MetricCard = ({ title, value, subtitle, color, isHeadline = false }) => (
    <div
      style={{
        background: "var(--paper-elevated)",
        border: "1px solid var(--border)",
        borderRadius: "var(--radius-lg)",
        padding: isHeadline ? "var(--space-6)" : "var(--space-5)",
        boxShadow: "var(--shadow-sm)",
        display: "flex",
        flexDirection: "column",
        ...(isHeadline && { borderLeft: `4px solid ${color}`, minWidth: "220px" }),
      }}
    >
      <div style={{ fontSize: "var(--text-xs)", fontWeight: "var(--font-medium)", textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--ink-muted)", marginBottom: "var(--space-2)" }}>
        {title}
      </div>
      <div style={{ fontSize: isHeadline ? "var(--text-3xl)" : "var(--text-2xl)", fontWeight: "var(--font-bold)", color, lineHeight: "var(--leading-tight)", fontFamily: "var(--font-sans)" }}>
        {value}
      </div>
      <div style={{ fontSize: "var(--text-xs)", color: "var(--ink-muted)", marginTop: "var(--space-1)" }}>
        {subtitle}
      </div>
    </div>
  );

  // Accuracy badge component
  const AccuracyBadge = ({ value, label }) => {
    const pct = value * 100;
    const bg = pct >= 80 ? "var(--trust-high-bg)" : pct >= 50 ? "var(--trust-medium-bg)" : "var(--trust-low-bg)";
    const color = pct >= 80 ? "var(--trust-high)" : pct >= 50 ? "var(--trust-medium)" : "var(--trust-low)";
    return (
      <span style={{ display: "inline-flex", alignItems: "center", gap: "var(--space-1)", padding: "var(--space-1) var(--space-2)", borderRadius: "var(--radius-sm)", fontSize: "var(--text-xs)", fontWeight: "var(--font-semibold)", fontFamily: "var(--font-sans)", background: bg, color }}>
        {pct.toFixed(1)}%
        {label && <span style={{ fontWeight: "var(--font-normal)", opacity: 0.8 }}>{label}</span>}
      </span>
    );
  };

  return (
    <div>
      {/* Header */}
      <header style={{ marginBottom: "var(--space-8)", paddingBottom: "var(--space-5)", borderBottom: "1px solid var(--border)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "var(--space-4)" }}>
          <div>
            <h1 style={{ margin: "0 0 var(--space-1)", fontSize: "var(--text-3xl)", fontWeight: "var(--font-semibold)", color: "var(--ink)", letterSpacing: "-0.02em" }}>
              Admin Dashboard
            </h1>
            <p style={{ margin: 0, fontSize: "var(--text-md)", color: "var(--ink-muted)" }}>
              IntelliDocs Agent Evaluation Metrics
            </p>
          </div>
          <div style={{ display: "flex", gap: "var(--space-3)", alignItems: "center", flexWrap: "wrap" }}>
            <label htmlFor="report-select" className="visually-hidden">Select evaluation report</label>
            <select
              id="report-select"
              value={selectedReport}
              onChange={(e) => handleReportSelect(e.target.value)}
              style={{
                padding: "var(--space-2) var(--space-3)",
                fontSize: "var(--text-sm)",
                fontFamily: "var(--font-sans)",
                color: "var(--ink)",
                background: "var(--paper-elevated)",
                border: "1px solid var(--border)",
                borderRadius: "var(--radius-md)",
                cursor: "pointer",
                minWidth: "280px",
              }}
            >
              {evalList.map((r) => (
                <option key={r.filename} value={r.filename}>
                  {r.filename} ({r.timestamp?.slice(0, 19).replace("T", " ")})
                </option>
              ))}
            </select>
            <span style={{ fontSize: "var(--text-xs)", color: "var(--ink-muted)", fontFamily: "var(--font-mono)" }}>
              Provider: {metadata.llm_provider} • {metadata.total_questions} questions
            </span>
          </div>
        </div>
      </header>

      {/* Key Metrics Cards - Headline metric gets visual weight */}
      <section style={{ marginBottom: "var(--space-8)" }}>
        <h2 style={{ margin: "0 0 var(--space-4)", fontSize: "var(--text-lg)", fontWeight: "var(--font-semibold)", color: "var(--ink)" }}>
          Key Metrics
        </h2>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))", gap: "var(--space-4)" }}>
          <MetricCard
            title="Path Accuracy"
            value={`${(summary.path_accuracy * 100).toFixed(1)}%`}
            subtitle="Router chose correct path"
            color="var(--accent)"
            isHeadline
          />
          <MetricCard
            title="Tool Accuracy"
            value={`${(summary.tool_accuracy * 100).toFixed(1)}%`}
            subtitle="Correct tool selected"
            color="var(--trust-high)"
          />
          <MetricCard
            title="Avg Answer Score"
            value={`${(summary.avg_answer_score * 100).toFixed(1)}%`}
            subtitle="Keyword match score"
            color="var(--trust-medium)"
          />
          <MetricCard
            title="Avg Latency"
            value={`${summary.avg_latency_ms?.toFixed(0) || 0}ms`}
            subtitle="Per question"
            color="var(--trust-medium)"
          />
          <MetricCard
            title="Total Cost"
            value={`$${summary.total_cost_usd?.toFixed(4) || 0}`}
            subtitle={`${summary.total_tokens || 0} tokens`}
            color="var(--ink)"
          />
          <MetricCard
            title="Error Rate"
            value={`${(summary.error_rate * 100).toFixed(1)}%`}
            subtitle="Failed evaluations"
            color={summary.error_rate > 0.1 ? "var(--trust-low)" : "var(--trust-high)"}
          />
        </div>
      </section>

      {/* Charts */}
      <section style={{ marginBottom: "var(--space-8)" }}>
        <EvalCharts 
          report={evalReport} 
          byCategory={byCategory}
        />
      </section>

      {/* Category Breakdown Table */}
      <section style={{ marginBottom: "var(--space-8)" }}>
        <h2 style={{ margin: "0 0 var(--space-4)", fontSize: "var(--text-lg)", fontWeight: "var(--font-semibold)", color: "var(--ink)" }}>
          Breakdown by Category
        </h2>
        <div style={{ overflowX: "auto", background: "var(--paper-elevated)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "var(--text-sm)" }}>
            <thead>
              <tr style={{ background: "var(--paper)", borderBottom: "1px solid var(--border)" }}>
                <th style={{ padding: "var(--space-3) var(--space-4)", textAlign: "left", fontWeight: "var(--font-semibold)", color: "var(--ink)", fontSize: "var(--text-xs)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Category</th>
                <th style={{ padding: "var(--space-3) var(--space-4)", textAlign: "right", fontWeight: "var(--font-semibold)", color: "var(--ink)", fontSize: "var(--text-xs)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Questions</th>
                <th style={{ padding: "var(--space-3) var(--space-4)", textAlign: "right", fontWeight: "var(--font-semibold)", color: "var(--ink)", fontSize: "var(--text-xs)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Path Accuracy</th>
                <th style={{ padding: "var(--space-3) var(--space-4)", textAlign: "right", fontWeight: "var(--font-semibold)", color: "var(--ink)", fontSize: "var(--text-xs)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Tool Accuracy</th>
                <th style={{ padding: "var(--space-3) var(--space-4)", textAlign: "right", fontWeight: "var(--font-semibold)", color: "var(--ink)", fontSize: "var(--text-xs)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Avg Score</th>
                <th style={{ padding: "var(--space-3) var(--space-4)", textAlign: "right", fontWeight: "var(--font-semibold)", color: "var(--ink)", fontSize: "var(--text-xs)", textTransform: "uppercase", letterSpacing: "0.05em" }}>Avg Latency</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(byCategory).map(([cat, stats]) => (
                <tr key={cat} style={{ borderBottom: "1px solid var(--border)" }}>
                  <td style={{ padding: "var(--space-3) var(--space-4)", fontWeight: "var(--font-medium)", color: "var(--ink)", textTransform: "capitalize" }}>{cat}</td>
                  <td style={{ padding: "var(--space-3) var(--space-4)", textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--ink-muted)" }}>{stats.total}</td>
                  <td style={{ padding: "var(--space-3) var(--space-4)", textAlign: "right" }}>
                    <AccuracyBadge value={stats.path_accuracy} />
                  </td>
                  <td style={{ padding: "var(--space-3) var(--space-4)", textAlign: "right" }}>
                    <AccuracyBadge value={stats.tool_accuracy} />
                  </td>
                  <td style={{ padding: "var(--space-3) var(--space-4)", textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--ink)" }}>
                    {(stats.avg_score * 100).toFixed(1)}%
                  </td>
                  <td style={{ padding: "var(--space-3) var(--space-4)", textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--ink-muted)" }}>
                    {stats.avg_latency.toFixed(0)}ms
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      {/* Human Evaluation Section */}
      <section>
        <h2 style={{ margin: "0 0 var(--space-4)", fontSize: "var(--text-lg)", fontWeight: "var(--font-semibold)", color: "var(--ink)" }}>
          Human Evaluation
        </h2>
        <div style={{ background: "var(--paper-elevated)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", padding: "var(--space-6)" }}>
          <p style={{ margin: "0 0 var(--space-5)", fontSize: "var(--text-sm)", color: "var(--ink-muted)" }}>
            Human evaluation scores complement automated metrics. Score each response on Relevance, Faithfulness, and Helpfulness (1–5).
          </p>
          <HumanEvalForm evalReport={evalReport} />
        </div>
      </section>

      <style jsx global>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

// Human evaluation form component
function HumanEvalForm({ evalReport }) {
  const [scores, setScores] = useState({});
  const [saved, setSaved] = useState(false);

  const results = evalReport.results || [];

  const handleScoreChange = (questionId, dimension, value) => {
    setScores(prev => ({
      ...prev,
      [questionId]: {
        ...prev[questionId],
        [dimension]: value,
      },
    }));
    setSaved(false);
  };

  const handleSave = () => {
    const payload = {
      eval_run_id: evalReport.metadata?.timestamp,
      human_scores: Object.entries(scores).map(([questionId, dims]) => ({
        question_id: questionId,
        ...dims,
      })),
      reviewer: "admin",
      date: new Date().toISOString(),
    };
    
    console.log("Human eval scores:", JSON.stringify(payload, null, 2));
    alert("Scores saved! (Check console for JSON — in production this would POST to backend)");
    setSaved(true);
  };

  return (
    <div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: "var(--space-4)", marginBottom: "var(--space-4)" }}>
        {results.slice(0, 10).map((r) => (
          <div key={r.id} style={{ background: "var(--paper)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", padding: "var(--space-4)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: "var(--space-2)", marginBottom: "var(--space-2)" }}>
              <span style={{ fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", fontWeight: "var(--font-medium)", color: "var(--accent)", background: "var(--accent-subtle)", padding: "var(--space-1) var(--space-2)", borderRadius: "var(--radius-sm)" }}>
                {r.id}
              </span>
              <span style={{ fontSize: "var(--text-xs)", fontWeight: "var(--font-medium)", textTransform: "capitalize", color: "var(--ink-muted)", background: "var(--border)", padding: "var(--space-1) var(--space-2)", borderRadius: "var(--radius-sm)" }}>
                {r.category}
              </span>
            </div>
            <div style={{ fontSize: "var(--text-sm)", color: "var(--ink)", marginBottom: "var(--space-3)", lineHeight: "var(--leading-relaxed)" }}>
              {r.question.slice(0, 120)}{r.question.length > 120 ? "…" : ""}
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "var(--space-2)" }}>
              {["relevance", "faithfulness", "helpfulness"].map((dim) => (
                <div key={dim} style={{ display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
                  <label style={{ width: "100px", fontSize: "var(--text-xs)", fontWeight: "var(--font-medium)", textTransform: "capitalize", color: "var(--ink-muted)" }}>{dim}</label>
                  <select
                    value={scores[r.id]?.[dim] || ""}
                    onChange={(e) => handleScoreChange(r.id, dim, parseInt(e.target.value))}
                    style={{
                      flex: 1,
                      padding: "var(--space-1) var(--space-2)",
                      fontSize: "var(--text-sm)",
                      fontFamily: "var(--font-sans)",
                      color: "var(--ink)",
                      background: "var(--paper-elevated)",
                      border: "1px solid var(--border)",
                      borderRadius: "var(--radius-sm)",
                      cursor: "pointer",
                    }}
                  >
                    <option value="">—</option>
                    <option value={1}>1 — Poor</option>
                    <option value={2}>2 — Below Average</option>
                    <option value={3}>3 — Adequate</option>
                    <option value={4}>4 — Good</option>
                    <option value={5}>5 — Excellent</option>
                  </select>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      <button
        onClick={handleSave}
        disabled={saved}
        style={{
          padding: "var(--space-3) var(--space-6)",
          fontSize: "var(--text-sm)",
          fontWeight: "var(--font-semibold)",
          fontFamily: "var(--font-sans)",
          color: "white",
          background: saved ? "var(--trust-high)" : "var(--accent)",
          border: "none",
          borderRadius: "var(--radius-md)",
          cursor: saved ? "not-allowed" : "pointer",
          transition: "background var(--transition-fast)",
        }}
        className="save-eval-btn"
      >
        {saved ? "Saved" : "Save Human Evaluation Scores"}
      </button>
    </div>
  );
}