import { forwardRef, type CSSProperties, type ReactEventHandler } from "react";

export const GAME_IFRAME_SANDBOX = "allow-scripts allow-forms";
export const GAME_IFRAME_CSP =
  "sandbox allow-scripts allow-forms; default-src 'self' 'unsafe-inline'; connect-src 'none'; object-src 'none'; frame-src 'none'; base-uri 'none'";

type Props = {
  title: string;
  src: string;
  className?: string;
  style?: CSSProperties;
  onLoad?: ReactEventHandler<HTMLIFrameElement>;
};

export const GameFrame = forwardRef<HTMLIFrameElement, Props>(function GameFrame(
  { title, src, className, style, onLoad },
  ref
) {
  return (
    <iframe
      ref={ref}
      className={className}
      title={title}
      src={src}
      onLoad={onLoad}
      style={style}
      sandbox={GAME_IFRAME_SANDBOX}
      allow=""
      referrerPolicy="no-referrer"
      {...{ csp: GAME_IFRAME_CSP }}
    />
  );
});
