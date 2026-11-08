export const MIN_ZOOM: number;
export const MAX_ZOOM: number;
export type CanvasTransform = { scale: number; x: number; y: number };
export function clampZoom(value: number): number;
export function fitZoom(width: number, height: number, viewportWidth: number, viewportHeight: number): number;
export function zoomAt(view: CanvasTransform, nextScale: number, point: { x: number; y: number }): CanvasTransform;
