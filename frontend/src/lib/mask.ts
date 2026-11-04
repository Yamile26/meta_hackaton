/**
 * Photo mask helpers (docs/contract.md, "Máscara de foto").
 * The mask is an RGBA PNG at full photo size, transparent background, one
 * fixed color per class, painted bottom → top: water, houses, vehicles, people.
 */

export type MaskClass = "water" | "houses" | "vehicles" | "people";

/** Contract colors, in paint order (bottom → top). */
export const MASK_CLASSES: { key: MaskClass; rgba: [number, number, number, number] }[] = [
  { key: "water", rgba: [56, 152, 236, 140] },
  { key: "houses", rgba: [163, 163, 163, 150] },
  { key: "vehicles", rgba: [250, 204, 21, 170] },
  { key: "people", rgba: [242, 107, 29, 190] },
];

export const maskCss = (rgba: [number, number, number, number]) => `rgba(${rgba[0]},${rgba[1]},${rgba[2]},${(rgba[3] / 255).toFixed(3)})`;

export type MaskCoverage = Record<MaskClass, number>;

/** Longest side used for pixel counting (fractions do not need full resolution). */
const ANALYSIS_MAX = 512;

/**
 * Share of the photo area covered by each class, computed in code from the
 * mask pixels (nearest contract color among non-transparent pixels).
 * These are AREA fractions (0–1), not object counts.
 */
export async function maskCoverage(mask: Blob): Promise<MaskCoverage> {
  const bmp = await createImageBitmap(mask);
  const scale = Math.min(1, ANALYSIS_MAX / Math.max(bmp.width, bmp.height));
  const w = Math.max(1, Math.round(bmp.width * scale));
  const h = Math.max(1, Math.round(bmp.height * scale));
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  if (!ctx) throw new Error("Canvas not available");
  ctx.imageSmoothingEnabled = false; // keep class colors exact when downscaling
  ctx.drawImage(bmp, 0, 0, w, h);
  bmp.close();
  const px = ctx.getImageData(0, 0, w, h).data;

  const counts: MaskCoverage = { water: 0, houses: 0, vehicles: 0, people: 0 };
  for (let i = 0; i < px.length; i += 4) {
    if (px[i + 3] < 16) continue; // transparent background
    let best = MASK_CLASSES[0].key;
    let bestD = Infinity;
    for (const c of MASK_CLASSES) {
      const d = (px[i] - c.rgba[0]) ** 2 + (px[i + 1] - c.rgba[1]) ** 2 + (px[i + 2] - c.rgba[2]) ** 2;
      if (d < bestD) {
        bestD = d;
        best = c.key;
      }
    }
    counts[best]++;
  }
  const total = w * h;
  return {
    water: counts.water / total,
    houses: counts.houses / total,
    vehicles: counts.vehicles / total,
    people: counts.people / total,
  };
}
