import { useI18n } from "../../i18n.jsx";

export default function StatusBadge({ status }) {
  const { t } = useI18n();
  return (
    <span className={`status-badge status-${status}`}>
      <span className="status-dot" />
      {t(`status.${status}`) || status}
    </span>
  );
}
