/**
 * SIMULATED photo mask for demo mode. Draws fixed shapes (not a real
 * segmentation) at the photo's own size, with the contract colors and paint
 * order, so the UI can be recorded without the API.
 */
import { MASK_CLASSES, type MaskClass } from "@/lib/mask";

type Shape = (ctx: CanvasRenderingContext2D, w: number, h: number) => void;

const SHAPES: Record<MaskClass, Shape[]> = {
  water: [
    (ctx, w, h) => {
      ctx.moveTo(0, h);
      ctx.lineTo(0, h * 0.62);
      for (let x = 0; x <= w; x += w / 24) ctx.lineTo(x, h * (0.62 + 0.025 * Math.sin((x / w) * Math.PI * 5)));
      ctx.lineTo(w, h);
      ctx.closePath();
    },
  ],
  houses: [
    (ctx, w, h) => ctx.rect(w * 0.06, h * 0.3, w * 0.22, h * 0.34),
    (ctx, w, h) => ctx.rect(w * 0.34, h * 0.24, w * 0.2, h * 0.4),
    (ctx, w, h) => ctx.rect(w * 0.7, h * 0.33, w * 0.24, h * 0.31),
  ],
  vehicles: [(ctx, w, h) => ctx.rect(w * 0.57, h * 0.56, w * 0.11, h * 0.1)],
  people: [
    (ctx, w, h) => ctx.ellipse(w * 0.3, h * 0.66, w * 0.018, h * 0.07, 0, 0, Math.PI * 2),
    (ctx, w, h) => ctx.ellipse(w * 0.36, h * 0.67, w * 0.016, h * 0.065, 0, 0, Math.PI * 2),
  ],
};

/** Returns a PNG mask (Blob) with the same width/height as the photo. */
export async function makeMockMask(photo: Blob): Promise<Blob> {
  const bmp = await createImageBitmap(photo);
  const { width: w, height: h } = bmp;
  bmp.close();
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("Canvas not available");
  // Bottom → top. Each shape replaces (not blends) the pixels it covers,
  // so every mask pixel has exactly one contract color.
  for (const cls of MASK_CLASSES) {
    for (const shape of SHAPES[cls.key]) {
      ctx.save();
      ctx.beginPath();
      shape(ctx, w, h);
      ctx.clip();
      ctx.clearRect(0, 0, w, h);
      ctx.fillStyle = `rgba(${cls.rgba[0]},${cls.rgba[1]},${cls.rgba[2]},${cls.rgba[3] / 255})`;
      ctx.fillRect(0, 0, w, h);
      ctx.restore();
    }
  }
  return new Promise((resolve, reject) => canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("Mask encoding failed"))), "image/png"));
}
