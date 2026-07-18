export default function PageHeader({ eyebrow, title, description, actions }) {
  return (
    <div className="page-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: 16 }}>
      <div>
        {eyebrow && <div className="eyebrow">{eyebrow}</div>}
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {actions && <div style={{ display: "flex", gap: 8 }}>{actions}</div>}
    </div>
  );
}
