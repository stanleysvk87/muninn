const LABELS = {
  processed: "Spracovane",
  failed: "Zlyhalo",
  pending: "Caka",
  processing: "Spracovava sa",
};

export default function StatusBadge({ status }) {
  return (
    <span className={`status-badge status-${status}`}>
      <span className="status-dot" />
      {LABELS[status] || status}
    </span>
  );
}
