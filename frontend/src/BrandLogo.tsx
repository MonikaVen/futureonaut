type Props = {
  className?: string;
  showText?: boolean;
};

export function BrandLogo({ className = "", showText = true }: Props) {
  return (
    <span className={`brand-logo${className ? ` ${className}` : ""}`}>
      <img src="/logo.png" alt="" className="brand-logo-icon" width={36} height={36} />
      {showText ? <span className="brand-logo-text">Futureonaut</span> : null}
    </span>
  );
}
