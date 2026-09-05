/**
 * Evaluation Charts component (Redesigned - Pass 2).
 * 
 * Renders charts for evaluation metrics using recharts.
 * Uses the app's color token system (CSS variables) for consistency.
 */

import { useMemo } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  LineChart,
  Line,
} from "recharts";

// Chart color palette - single source of truth matching CSS variables in index.css
// These values MUST stay in sync with :root { --accent, --trust-high, --trust-medium, --trust-low }
const CHART_COLORS = {
  rag: "#1F6FEB",        // --accent
  tool: "#1A7F37",       // --trust-high
  clarify: "#9A6700",    // --trust-medium
  trick: "#BF2600",      // --trust-low
  fallback: "#8C959F",   // --border-strong (replaces #666)
  pieDefault: "#8884d8", // Default pie fill (recharts default)
};

const CATEGORY_LABELS = {
  rag: "RAG",
  tool: "Tool",
  clarify: "Clarify",
  trick: "Trick",
};

// Shared chart container styles
const ChartCard = ({ title, children }) => (
  <div className="chart-card" style={{ background: "var(--paper-elevated)", border: "1px solid var(--border)", borderRadius: "var(--radius-lg)", padding: "var(--space-5)" }}>
    <h3 style={{ margin: "0 0 var(--space-4)", fontSize: "var(--text-sm)", fontWeight: "var(--font-semibold)", color: "var(--ink)" }}>{title}</h3>
    <div style={{ height: "300px" }}>{children}</div>
  </div>
);

// Shared tooltip formatter
const tooltipFormatter = (value, name) => [value, name];

export default function EvalCharts({ report, byCategory }) {
  if (!report || !byCategory) {
    return <div style={{ color: "var(--ink-muted)", textAlign: "center", padding: "var(--space-8)" }}>No data to display</div>;
  }

  const summary = report.summary || {};
  const results = report.results || [];

  // Prepare data for charts
  const categoryData = useMemo(() => Object.entries(byCategory).map(([cat, stats]) => ({
    category: CATEGORY_LABELS[cat] || cat,
    pathAccuracy: (stats.path_accuracy * 100).toFixed(1),
    toolAccuracy: (stats.tool_accuracy * 100).toFixed(1),
    avgScore: (stats.avg_score * 100).toFixed(1),
    avgLatency: stats.avg_latency.toFixed(0),
    total: stats.total,
    color: CHART_COLORS[cat] || CHART_COLORS.fallback,
  })), [byCategory]);

  const pathDistribution = useMemo(() => {
    const dist = results.reduce((acc, r) => {
      const path = r.actual_path || "unknown";
      acc[path] = (acc[path] || 0) + 1;
      return acc;
    }, {});
    return Object.entries(dist).map(([path, count]) => ({
      path: path.charAt(0).toUpperCase() + path.slice(1),
      count,
      color: CHART_COLORS[path] || CHART_COLORS.fallback,
    }));
  }, [results]);

  const confidenceDistribution = useMemo(() => {
    const dist = results.reduce((acc, r) => {
      if (r.confidence) {
        acc[r.confidence] = (acc[r.confidence] || 0) + 1;
      }
      return acc;
    }, {});
    return Object.entries(dist).map(([conf, count]) => ({
      confidence: conf.charAt(0).toUpperCase() + conf.slice(1),
      count,
      color: conf === "high" ? CHART_COLORS.tool : conf === "medium" ? CHART_COLORS.clarify : CHART_COLORS.trick,
    }));
  }, [results]);

  // Latency by category
  const latencyData = useMemo(() => categoryData.map(d => ({
    category: d.category,
    latency: parseFloat(d.avgLatency),
    color: d.color,
  })), [categoryData]);

  // Custom tooltip content
  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div style={{ background: "var(--paper-elevated)", border: "1px solid var(--border)", borderRadius: "var(--radius-md)", padding: "var(--space-3)", boxShadow: "var(--shadow-md)" }}>
          <p style={{ margin: "0 0 var(--space-2)", fontSize: "var(--text-xs)", fontWeight: "var(--font-semibold)", color: "var(--ink-muted)", textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</p>
          {payload.map((entry, index) => (
            <p key={index} style={{ margin: 0, fontSize: "var(--text-sm)", color: entry.color, display: "flex", alignItems: "center", gap: "var(--space-2)" }}>
              <span style={{ width: "8px", height: "8px", borderRadius: "var(--radius-full)", background: entry.color }} />
              <span style={{ fontWeight: "var(--font-medium)" }}>{entry.name}: </span>
              <span style={{ fontFamily: "var(--font-mono)" }}>{entry.value}</span>
            </p>
          ))}
        </div>
      );
    }
    return null;
  };

  return (
    <div className="eval-charts" style={{ display: "flex", flexDirection: "column", gap: "var(--space-5)" }}>
      {/* Row 1: Path Accuracy & Tool Accuracy by Category */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))", gap: "var(--space-5)" }}>
        <ChartCard title="Path Accuracy by Category">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={categoryData} layout="vertical" margin={{ top: 10, right: 10, left: 0, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
              <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11, fill: "var(--ink-muted)", fontFamily: "var(--font-mono)" }} tickLine={false} axisLine={false} />
              <YAxis type="category" dataKey="category" width={80} tick={{ fontSize: 12, fill: "var(--ink)", fontFamily: "var(--font-sans)" }} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Bar dataKey="pathAccuracy" name="Path Accuracy" fill="var(--accent)" radius={[0, 4, 4, 0]} maxBarSize={40} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Tool Accuracy by Category">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={categoryData} layout="vertical" margin={{ top: 10, right: 10, left: 0, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
              <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11, fill: "var(--ink-muted)", fontFamily: "var(--font-mono)" }} tickLine={false} axisLine={false} />
              <YAxis type="category" dataKey="category" width={80} tick={{ fontSize: 12, fill: "var(--ink)", fontFamily: "var(--font-sans)" }} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Bar dataKey="toolAccuracy" name="Tool Accuracy" fill="var(--trust-high)" radius={[0, 4, 4, 0]} maxBarSize={40} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Row 2: Answer Score & Latency */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))", gap: "var(--space-5)" }}>
        <ChartCard title="Avg Answer Score by Category">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={categoryData} layout="vertical" margin={{ top: 10, right: 10, left: 0, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
              <XAxis type="number" domain={[0, 100]} tickFormatter={(v) => `${v}%`} tick={{ fontSize: 11, fill: "var(--ink-muted)", fontFamily: "var(--font-mono)" }} tickLine={false} axisLine={false} />
              <YAxis type="category" dataKey="category" width={80} tick={{ fontSize: 12, fill: "var(--ink)", fontFamily: "var(--font-sans)" }} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Bar dataKey="avgScore" name="Answer Score" fill="var(--trust-medium)" radius={[0, 4, 4, 0]} maxBarSize={40} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Avg Latency by Category">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={latencyData} layout="vertical" margin={{ top: 10, right: 10, left: 0, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
              <XAxis type="number" tickFormatter={(v) => `${v}ms`} tick={{ fontSize: 11, fill: "var(--ink-muted)", fontFamily: "var(--font-mono)" }} tickLine={false} axisLine={false} />
              <YAxis type="category" dataKey="category" width={80} tick={{ fontSize: 12, fill: "var(--ink)", fontFamily: "var(--font-sans)" }} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Bar dataKey="latency" name="Latency (ms)" fill="var(--trust-medium)" radius={[0, 4, 4, 0]} maxBarSize={40} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Row 3: Path Distribution Pie & Confidence Distribution Pie */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))", gap: "var(--space-5)" }}>
        <ChartCard title="Router Path Distribution">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={pathDistribution}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={100}
                fill={CHART_COLORS.pieDefault}
                dataKey="count"
                nameKey="path"
                label={({ path, percent }) => `${path} ${(percent * 100).toFixed(0)}%`}
                labelLine={false}
              >
                {pathDistribution.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
              <Legend layout="vertical" align="right" verticalAlign="middle" iconType="circle" iconSize={8} wrapperStyle={{ paddingRight: 20 }} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Confidence Distribution">
          <ResponsiveContainer width="100%" height="100%">
            <PieChart>
              <Pie
                data={confidenceDistribution}
                cx="50%"
                cy="50%"
                innerRadius={60}
                outerRadius={100}
                fill={CHART_COLORS.pieDefault}
                dataKey="count"
                nameKey="confidence"
                label={({ confidence, percent }) => `${confidence} ${(percent * 100).toFixed(0)}%`}
                labelLine={false}
              >
                {confidenceDistribution.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip content={<CustomTooltip />} />
              <Legend layout="vertical" align="right" verticalAlign="middle" iconType="circle" iconSize={8} wrapperStyle={{ paddingRight: 20 }} />
            </PieChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>

      {/* Row 4: Question Count by Category */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(400px, 1fr))", gap: "var(--space-5)" }}>
        <ChartCard title="Questions per Category">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={categoryData} layout="vertical" margin={{ top: 10, right: 10, left: 0, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="var(--border)" />
              <XAxis type="number" tick={{ fontSize: 11, fill: "var(--ink-muted)", fontFamily: "var(--font-mono)" }} tickLine={false} axisLine={false} />
              <YAxis type="category" dataKey="category" width={80} tick={{ fontSize: 12, fill: "var(--ink)", fontFamily: "var(--font-sans)" }} tickLine={false} axisLine={false} />
              <Tooltip content={<CustomTooltip />} />
              <Legend />
              <Bar dataKey="total" name="Questions" fill="var(--ink-muted)" radius={[0, 4, 4, 0]} maxBarSize={40} />
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard title="Summary Metrics">
          <div style={{ padding: "var(--space-4)" }}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(2, 1fr)", gap: "var(--space-4)" }}>
              <SummaryStat label="Total Questions" value={summary.total_questions || results.length} />
              <SummaryStat label="Path Accuracy" value={`${(summary.path_accuracy * 100).toFixed(1)}%`} />
              <SummaryStat label="Tool Accuracy" value={`${(summary.tool_accuracy * 100).toFixed(1)}%`} />
              <SummaryStat label="Avg Answer Score" value={`${(summary.avg_answer_score * 100).toFixed(1)}%`} />
              <SummaryStat label="Avg Latency" value={`${summary.avg_latency_ms?.toFixed(0) || 0}ms`} />
              <SummaryStat label="Total Cost" value={`$${summary.total_cost_usd?.toFixed(4) || 0}`} />
              <SummaryStat label="Total Tokens" value={summary.total_tokens || 0} />
              <SummaryStat label="Error Rate" value={`${(summary.error_rate * 100).toFixed(1)}%`} />
            </div>
          </div>
        </ChartCard>
      </div>
    </div>
  );
}

function SummaryStat({ label, value }) {
  return (
    <div style={{ textAlign: "center", padding: "var(--space-4)", background: "var(--paper)", borderRadius: "var(--radius-md)" }}>
      <div style={{ fontSize: "var(--text-xl)", fontWeight: "var(--font-bold)", color: "var(--accent)", fontFamily: "var(--font-sans)" }}>{value}</div>
      <div style={{ fontSize: "var(--text-xs)", color: "var(--ink-muted)", marginTop: "var(--space-1)", textTransform: "uppercase", letterSpacing: "0.05em" }}>{label}</div>
    </div>
  );
}