import React, { useEffect, useRef } from 'react';

type Media = { data: string; mime: string; width: number; height: number };
type Clip = { name: string; loop: boolean; duration_ms: number; frames: unknown[] };

// Native APNG playback retains source pixels/timing. Only one-shot previews are
// replayed for the gallery; this does not change saved clips or game resources.
export function ImagePreview({ media, label, loop = true, clip, replay = 0 }: {
  media: Media; label: string; loop?: boolean; clip?: Clip; replay?: number;
}) {
  const image = useRef<HTMLImageElement>(null);
  useEffect(() => {
    const target = image.current;
    if (!target) return;
    const blob = new Blob([Uint8Array.from(atob(media.data), ch => ch.charCodeAt(0))], { type: media.mime });
    let url: string | undefined, timer: ReturnType<typeof setTimeout> | undefined, closed = false;
    const stop = () => { clearTimeout(timer); target.onload = null; if (url) URL.revokeObjectURL(url); url = undefined; };
    const play = () => {
      stop(); if (closed || document.hidden) return;
      url = URL.createObjectURL(blob);
      target.onload = () => { if (!closed && !document.hidden && loop && clip && !clip.loop && clip.frames.length > 1) timer = setTimeout(play, clip.duration_ms); };
      target.src = url;
    };
    play(); document.addEventListener('visibilitychange', play);
    return () => { closed = true; stop(); document.removeEventListener('visibilitychange', play); };
  }, [media, loop, clip?.name, clip?.loop, clip?.duration_ms, replay]);
  return <div className="compact-preview"><img ref={image} alt={label} draggable={false}/></div>;
}
