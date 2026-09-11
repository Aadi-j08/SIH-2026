/**
 * Photos live in frontend/public/img (see the README there). A slot hides
 * itself until its file exists, so a missing photo never leaves a hole.
 */
import { useEffect, useState } from "react";

export const img = (name: string) => `${import.meta.env.BASE_URL}img/${name}`;

export function Photo({ name, alt, className = "photo", style }: { name: string; alt: string; className?: string; style?: React.CSSProperties }) {
  const [missing, setMissing] = useState(false);
  if (missing) return null;
  return <img className={className} src={img(name)} alt={alt} loading="lazy" style={style} onError={() => setMissing(true)} />;
}

/** True once the browser has confirmed the file exists; used for background photos. */
export function useImageExists(name: string): boolean {
  const [exists, setExists] = useState(false);
  useEffect(() => {
    const probe = new Image();
    probe.onload = () => setExists(true);
    probe.src = img(name);
  }, [name]);
  return exists;
}
