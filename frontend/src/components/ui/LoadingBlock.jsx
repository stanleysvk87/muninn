import { useI18n } from "../../i18n.jsx";

export default function LoadingBlock({ children }) {
  const { t } = useI18n();
  return <div className="loading-block">{children || t("common.loading")}</div>;
}
