export const MIN_ZOOM = 1 / 256;
export const MAX_ZOOM = 32;
export function clampZoom(value) { return Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, value)); }
export function fitZoom(width, height, viewportWidth, viewportHeight) {
  const fit = Math.min((viewportWidth - 64) / width, (viewportHeight - 64) / height, 8);
  return clampZoom(fit >= 1 ? Math.max(1, Math.floor(fit)) : fit);
}
export function zoomAt(view, nextScale, point) {
  const scale = clampZoom(nextScale), ratio = scale / view.scale;
  return { scale, x: point.x - (point.x - view.x) * ratio, y: point.y - (point.y - view.y) * ratio };
}
