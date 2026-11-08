import React, { useEffect, useId, useRef, useState } from 'react';
import { Button, Switch, Text } from '@radix-ui/themes';
import { Select } from './Select';
import { fitZoom, zoomAt, type CanvasTransform } from './canvas-math.mjs';

type ImageData = { data: string; mime: string; width: number; height: number };
type Clip = { name: string; loop: boolean; duration_ms: number; frames: unknown[] };

export function AssetCanvas({ image: data, label, sourceScale = 1, loop = true, clip, replay = 0, fixedScale, initialScale }: {
  image: ImageData; label: string; sourceScale?: number; loop?: boolean; clip?: Clip; replay?: number; fixedScale?: number; initialScale?: number;
}) {
  const helpID = useId();
  const surface = useRef<HTMLDivElement>(null), image = useRef<HTMLImageElement>(null);
  const [view, setView] = useState<CanvasTransform>({ scale: fixedScale || 1, x: 0, y: 0 });
  const current = useRef(view), fitting = useRef(!fixedScale);
  const [background, setBackground] = useState('checker'), [grid, setGrid] = useState(false), [dragging, setDragging] = useState(false);
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  useEffect(() => {
    const release = (event: PointerEvent) => { pointers.current.delete(event.pointerId); setDragging(pointers.current.size > 0); };
    const blur = () => { for (const id of pointers.current.keys()) if (surface.current?.hasPointerCapture(id)) surface.current.releasePointerCapture(id); pointers.current.clear(); setDragging(false); };
    window.addEventListener('pointerup', release); window.addEventListener('pointercancel', release);
    window.addEventListener('blur', blur);
    return () => { blur(); window.removeEventListener('pointerup', release); window.removeEventListener('pointercancel', release); window.removeEventListener('blur', blur); };
  }, []);
  const width = data.width / sourceScale, height = data.height / sourceScale;
  const update = (next: CanvasTransform) => { current.current = next; setView(next); };
  const reset = (scale?: number) => {
    const bounds = surface.current?.getBoundingClientRect();
    fitting.current = scale === undefined;
    update({ scale: scale ?? fitZoom(width, height, bounds?.width ?? 500, bounds?.height ?? 400), x: 0, y: 0 });
  };
  const zoom = (scale: number, point = { x: 0, y: 0 }) => { fitting.current = false; update(zoomAt(current.current, scale, point)); };
  useEffect(() => {
    reset(fixedScale || initialScale || undefined);
    const observer = new ResizeObserver(() => { if (fitting.current) reset(); });
    if (surface.current) observer.observe(surface.current);
    return () => observer.disconnect();
  }, [width, height, fixedScale, initialScale]);
  useEffect(() => {
    const target = surface.current;
    if (!target || fixedScale) return;
    const wheel = (event: WheelEvent) => {
      // Normal wheel motion must scroll the page, never trap the user over art.
      // Trackpad pinch generates ctrl+wheel; deliberate mouse zoom uses Ctrl/Cmd.
      if (!event.ctrlKey && !event.metaKey) return;
      event.preventDefault();
      const bounds = target.getBoundingClientRect();
      const delta = event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? bounds.height : 1);
      zoom(current.current.scale * Math.exp(-Math.max(-150, Math.min(150, delta)) * .006), { x: event.clientX - bounds.left - bounds.width / 2, y: event.clientY - bounds.top - bounds.height / 2 });
    };
    target.addEventListener('wheel', wheel, { passive: false });
    return () => target.removeEventListener('wheel', wheel);
  }, [fixedScale]);
  useEffect(() => {
    const target = image.current;
    if (!target) return;
    const raw = Uint8Array.from(atob(data.data), ch => ch.charCodeAt(0));
    const blob = new Blob([raw], { type: data.mime });
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
  }, [data, loop, clip?.name, clip?.loop, clip?.duration_ms, replay]);
  const local = (event: React.PointerEvent<HTMLDivElement>) => {
    const bounds = event.currentTarget.getBoundingClientRect();
    return { x: event.clientX - bounds.left - bounds.width / 2, y: event.clientY - bounds.top - bounds.height / 2 };
  };
  const end = (event: React.PointerEvent<HTMLDivElement>) => {
    pointers.current.delete(event.pointerId); setDragging(pointers.current.size > 0);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
  };
  return <section className="asset-canvas" aria-label={`${label} canvas`}>
    <div className="canvas-toolbar">
      {!fixedScale && <><Button size="1" variant="soft" onClick={() => reset()}>Fit</Button><Button size="1" variant="soft" onClick={() => reset(1)}>1:1</Button><Button size="1" variant="ghost" aria-label="Zoom out" onClick={() => zoom(current.current.scale / 1.5)}>−</Button><input className="zoom-slider" type="range" min="-8" max="5" step=".05" value={Math.log2(view.scale)} aria-label="Canvas zoom" onChange={event => zoom(2 ** Number(event.target.value))}/><Button size="1" variant="ghost" aria-label="Zoom in" onClick={() => zoom(current.current.scale * 1.5)}>+</Button></>}
      <output className="zoom-value" aria-label="Zoom level">{Math.round(view.scale * 100)}%</output>
      <Select.Root value={background} onValueChange={setBackground}><Select.Trigger aria-label="Canvas background"/><Select.Content><Select.Item value="checker">Checkerboard</Select.Item><Select.Item value="dark">Dark</Select.Item><Select.Item value="light">Light</Select.Item></Select.Content></Select.Root>
      <Text as="label" size="1"><span className="canvas-grid-control"><Switch size="1" checked={grid} onCheckedChange={setGrid}/>Pixel grid</span></Text>
      {!fixedScale && <Button size="1" variant="ghost" onClick={() => reset()}>Reset view</Button>}
    </div>
    <div ref={surface} className={`canvas-surface canvas-bg-${background} ${dragging ? 'panning' : ''}`} tabIndex={0} role="region" aria-label={`Pan and zoom ${label}`} aria-describedby={helpID} data-scale={view.scale} data-pan-x={view.x} data-pan-y={view.y}
      onDoubleClick={() => reset(fixedScale || undefined)}
      onPointerDown={event => { if (event.button !== 0) return; event.currentTarget.focus({ preventScroll: true }); event.currentTarget.setPointerCapture(event.pointerId); pointers.current.set(event.pointerId, local(event)); setDragging(true); }}
      onPointerMove={event => {
        const before = pointers.current.get(event.pointerId); if (!before) return;
        if (event.pointerType === 'mouse' && !(event.buttons & 1)) { end(event); return; }
        if (!event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.setPointerCapture(event.pointerId);
        const next = local(event), values = [...pointers.current.entries()], other = values.find(([id]) => id !== event.pointerId)?.[1];
        if (other && !fixedScale) {
          const oldDistance = Math.hypot(before.x - other.x, before.y - other.y), distance = Math.hypot(next.x - other.x, next.y - other.y);
          if (oldDistance > 2) {
            const center = { x: (before.x + other.x) / 2, y: (before.y + other.y) / 2 };
            const changed = zoomAt(current.current, current.current.scale * distance / oldDistance, center);
            fitting.current = false; update({ ...changed, x: changed.x + (next.x - before.x) / 2, y: changed.y + (next.y - before.y) / 2 });
          }
        } else { fitting.current = false; update({ ...current.current, x: current.current.x + next.x - before.x, y: current.current.y + next.y - before.y }); }
        pointers.current.set(event.pointerId, next);
      }} onPointerUp={end} onPointerCancel={end} onLostPointerCapture={event => { if (!event.buttons) end(event); }}
      onKeyDown={event => {
        if (event.key === 'Escape' || event.ctrlKey || event.metaKey || event.altKey) return;
        if (['+', '=', '-', '0', '1', 'f', 'F', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
          event.preventDefault();
          if (event.key === '0' || event.key.toLowerCase() === 'f') reset(fixedScale || undefined);
          else if (event.key === '1' && !fixedScale) reset(1);
          else if (['+', '=', '-'].includes(event.key) && !fixedScale) zoom(current.current.scale * (event.key === '-' ? 1 / 1.5 : 1.5));
          else if (event.key.startsWith('Arrow')) { fitting.current = false; update({ ...current.current, x: current.current.x + (event.key === 'ArrowLeft' ? -32 : event.key === 'ArrowRight' ? 32 : 0), y: current.current.y + (event.key === 'ArrowUp' ? -32 : event.key === 'ArrowDown' ? 32 : 0) }); }
        }
      }}>
      <div className="canvas-origin" aria-hidden="true"/>
      <div className="canvas-art-plane" style={{ width: width * view.scale, height: height * view.scale, left: `calc(50% + ${view.x}px)`, top: `calc(50% + ${view.y}px)` }}>
        <img ref={image} alt={label} draggable={false}/>
        {grid && view.scale >= 4 && <div className="canvas-pixel-grid" style={{ backgroundSize: `${view.scale}px ${view.scale}px` }}/>}</div>
      <span className="canvas-dimensions">{width} × {height} px</span>
    </div>
    <div className="canvas-status"><Text id={helpID} size="1" color="gray">{fixedScale ? 'Matched scale · drag to pan' : 'Scroll page · Ctrl/Cmd + scroll to zoom · drag to pan'}</Text><Text size="1" color="gray">{grid && view.scale < 4 ? 'Grid appears at 400%+' : 'Double-click to fit'}</Text></div>
  </section>;
}
