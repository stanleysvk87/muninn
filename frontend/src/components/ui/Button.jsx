export default function Button({ variant = "primary", children, className = "", ...rest }) {
  return (
    <button className={`btn btn-${variant} ${className}`} {...rest}>
      {children}
    </button>
  );
}
