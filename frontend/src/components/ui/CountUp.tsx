import { useState, useEffect, useRef } from 'react';
import { prefersReducedMotion } from '../../utils/dashboard';

interface CountUpProps {
  end: number;
  duration?: number;
  decimals?: number;
  className?: string;
  style?: React.CSSProperties;
}

function formatNumber(n: number, decimals: number): string {
  const parts = n.toFixed(decimals).split('.');
  parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return parts.join('.');
}

export default function CountUp({ end, duration = 800, decimals = 0, className = '', style }: CountUpProps) {
  const [display, setDisplay] = useState(() => formatNumber(end, decimals));
  const prevEnd = useRef(end);
  const frameRef = useRef(0);
  const [pulse, setPulse] = useState(false);

  useEffect(() => {
    const start = prevEnd.current;
    const diff = end - start;
    if (Math.abs(diff) < 0.001) {
      setDisplay(formatNumber(end, decimals));
      return;
    }
    if (prefersReducedMotion()) {
      setDisplay(formatNumber(end, decimals));
      prevEnd.current = end;
      return;
    }
    const startTime = performance.now();

    // quintic ease-out for dramatic deceleration
    const easeOutQuint = (t: number) => 1 - Math.pow(1 - t, 5);

    const tick = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = easeOutQuint(progress);
      const current = start + diff * eased;
      setDisplay(formatNumber(current, decimals));
      if (progress < 1) {
        frameRef.current = requestAnimationFrame(tick);
      } else {
        // subtle pulse on completion for non-zero changes
        if (Math.abs(diff) > 0.5) {
          setPulse(true);
          setTimeout(() => setPulse(false), 350);
        }
      }
    };
    frameRef.current = requestAnimationFrame(tick);
    prevEnd.current = end;

    return () => cancelAnimationFrame(frameRef.current);
  }, [end, duration, decimals]);

  return (
    <span className={`${className} ${pulse ? 'animate-number-pulse' : ''}`} style={style}>
      {display}
    </span>
  );
}
