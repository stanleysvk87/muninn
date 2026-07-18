export default function Card({ children, hover = false, className = "", ...rest }) {
  return (
    <div className={`card ${hover ? "card-hover" : ""} ${className}`} {...rest}>
      {children}
    </div>
  );
}
