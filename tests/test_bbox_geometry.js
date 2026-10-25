/**
 * Verification test for Bounding Box Render Geometry & Clamping
 * Validates:
 * 1. Landscape, Portrait, and Square images
 * 2. Proper letterbox calculation (offsetX, offsetY)
 * 3. Exact matching of rendered pixels without axis inversion
 * 4. Boundary clamping so boxes and labels never enter letterbox bars
 */
const assert = require('assert');

// Ported identical functions from workspace.js
function getImageRenderGeometry(naturalW, naturalH, elemW, elemH) {
  if (!naturalW || !naturalH || elemW <= 0 || elemH <= 0) return null;

  const imgAspect = naturalW / naturalH;
  const elemAspect = elemW / elemH;
  let renderW, renderH, offsetX, offsetY;

  if (elemAspect > imgAspect) {
    // Horizontal letterbox (black bars on left & right)
    renderH = elemH;
    renderW = elemH * imgAspect;
    offsetX = (elemW - renderW) / 2;
    offsetY = 0;
  } else {
    // Vertical letterbox (black bars on top & bottom)
    renderW = elemW;
    renderH = elemW / imgAspect;
    offsetX = 0;
    offsetY = (elemH - renderH) / 2;
  }

  return {
    naturalW, naturalH, elemW, elemH,
    renderW, renderH, offsetX, offsetY,
    scaleX: renderW / naturalW,
    scaleY: renderH / naturalH
  };
}

function extractNormalizedBox(obj, geom) {
  if (!obj) return null;
  if (Array.isArray(obj.box_normalized) && obj.box_normalized.length === 4) {
    let [c1, c2, c3, c4] = obj.box_normalized.map(Number);
    let x1 = Math.min(c1, c3);
    let y1 = Math.min(c2, c4);
    let x2 = Math.max(c1, c3);
    let y2 = Math.max(c2, c4);
    return {
      x1: Math.max(0, Math.min(1, x1)),
      y1: Math.max(0, Math.min(1, y1)),
      x2: Math.max(0, Math.min(1, x2)),
      y2: Math.max(0, Math.min(1, y2)),
    };
  }
  if (Array.isArray(obj.box_pixels) && obj.box_pixels.length === 4 && geom.naturalW && geom.naturalH) {
    let [px1, py1, px2, py2] = obj.box_pixels.map(Number);
    let x1 = Math.min(px1, px2) / geom.naturalW;
    let y1 = Math.min(py1, py2) / geom.naturalH;
    let x2 = Math.max(px1, px2) / geom.naturalW;
    let y2 = Math.max(py1, py2) / geom.naturalH;
    return {
      x1: Math.max(0, Math.min(1, x1)),
      y1: Math.max(0, Math.min(1, y1)),
      x2: Math.max(0, Math.min(1, x2)),
      y2: Math.max(0, Math.min(1, y2)),
    };
  }
  return null;
}

function computeClampedRenderBox(obj, geom) {
  const norm = extractNormalizedBox(obj, geom);
  if (!norm) return null;

  const minX = geom.offsetX;
  const maxX = geom.offsetX + geom.renderW;
  const minY = geom.offsetY;
  const maxY = geom.offsetY + geom.renderH;

  let boxX = geom.offsetX + norm.x1 * geom.renderW;
  let boxY = geom.offsetY + norm.y1 * geom.renderH;
  let boxW = (norm.x2 - norm.x1) * geom.renderW;
  let boxH = (norm.y2 - norm.y1) * geom.renderH;

  boxX = Math.max(minX, Math.min(maxX, boxX));
  boxY = Math.max(minY, Math.min(maxY, boxY));
  boxW = Math.max(0, Math.min(maxX - boxX, boxW));
  boxH = Math.max(0, Math.min(maxY - boxY, boxH));

  const labelHeight = 18;
  const labelWidth = 60; // approximate
  let labelY = boxY - labelHeight;
  if (labelY < minY) {
    labelY = boxY; // flips inside
  }
  let labelX = Math.max(minX, Math.min(maxX - labelWidth, boxX));

  return { boxX, boxY, boxW, boxH, labelX, labelY, minX, maxX, minY, maxY };
}

// ==========================================
// TEST SUITE
// ==========================================
console.log("Running Bounding Box Alignment & Geometry Verification...\n");

// Test 1: Landscape Image (16:9, e.g. 2752x1536) in letterboxed container (800x520)
{
  const geom = getImageRenderGeometry(2752, 1536, 800, 520);
  // elemAspect = 800/520 = 1.538, imgAspect = 2752/1536 = 1.7916
  // elemAspect < imgAspect => vertical letterbox (black bars top & bottom)
  assert.strictEqual(geom.offsetX, 0, "Landscape offsetX should be 0 when constrained by width");
  assert(geom.offsetY > 0, "Landscape offsetY should have letterbox padding");
  assert.strictEqual(Math.round(geom.renderW), 800);
  assert.strictEqual(Math.round(geom.renderH), Math.round(800 / (2752 / 1536)));

  const obj = {
    label: "person",
    box_normalized: [0.1, 0.2, 0.4, 0.8], // x1, y1, x2, y2
    confidence: 0.89
  };
  const res = computeClampedRenderBox(obj, geom);
  assert(res.boxX >= res.minX && res.boxX + res.boxW <= res.maxX, "Box X bounds must stay within rendered image");
  assert(res.boxY >= res.minY && res.boxY + res.boxH <= res.maxY, "Box Y bounds must stay within rendered image");
  assert(res.labelY >= res.minY, "Label Y must not overflow into top letterbox bar");
  console.log("✔ Test 1: Landscape 16:9 letterboxed image PASS");
}

// Test 2: Portrait Image (9:16, e.g. 1080x1920) in landscape container (800x520)
{
  const geom = getImageRenderGeometry(1080, 1920, 800, 520);
  // elemAspect = 800/520 = 1.538, imgAspect = 1080/1920 = 0.5625
  // elemAspect > imgAspect => horizontal letterbox (bars left & right)
  assert(geom.offsetX > 0, "Portrait offsetX should have horizontal letterbox padding");
  assert.strictEqual(geom.offsetY, 0, "Portrait offsetY should be 0 when constrained by height");
  assert.strictEqual(Math.round(geom.renderH), 520);
  assert.strictEqual(Math.round(geom.renderW), Math.round(520 * (1080 / 1920)));

  const obj = {
    label: "suspect",
    box_normalized: [0.05, 0.02, 0.95, 0.98],
    confidence: 0.92
  };
  const res = computeClampedRenderBox(obj, geom);
  assert(res.boxX >= res.minX, "Box X cannot bleed into left letterbox");
  assert(res.boxX + res.boxW <= res.maxX, "Box X cannot bleed into right letterbox");
  assert(res.labelX >= res.minX, "Label cannot bleed into left letterbox");
  assert(res.labelX + 60 <= res.maxX, "Label cannot bleed into right letterbox");
  console.log("✔ Test 2: Portrait 9:16 letterboxed image PASS");
}

// Test 3: Square Image (1:1, 1000x1000) in 800x520 container
{
  const geom = getImageRenderGeometry(1000, 1000, 800, 520);
  // elemAspect = 1.538 > imgAspect = 1.0 => horizontal letterbox
  assert(geom.offsetX > 0, "Square image in wider container has horizontal letterbox");
  assert.strictEqual(geom.offsetY, 0);
  assert.strictEqual(geom.renderW, 520);
  assert.strictEqual(geom.renderH, 520);
  console.log("✔ Test 3: Square 1:1 image PASS");
}

// Test 4: Top edge bounding box (y1 = 0) flips label INSIDE box
{
  const geom = getImageRenderGeometry(2000, 1000, 800, 520);
  const topEdgeObj = {
    label: "cctv_camera",
    box_normalized: [0.2, 0.0, 0.5, 0.3], // touches top y=0
    confidence: 0.95
  };
  const res = computeClampedRenderBox(topEdgeObj, geom);
  assert.strictEqual(res.labelY, res.boxY, "Label must flip inside box when y1 is at top boundary");
  assert(res.labelY >= res.minY, "Label must remain within image content, not outer container");
  console.log("✔ Test 4: Top-edge label flip PASS");
}

// Test 5: Coordinate Order Verification (no inverted X/Y axes)
{
  const geom = getImageRenderGeometry(1000, 500, 500, 250);
  // An object located in top-left: x1=0.1, y1=0.2, x2=0.3, y2=0.4
  const obj = {
    box_normalized: [0.1, 0.2, 0.3, 0.4],
    confidence: 0.8
  };
  const norm = extractNormalizedBox(obj, geom);
  assert.strictEqual(norm.x1, 0.1, "x1 must be horizontal coordinate");
  assert.strictEqual(norm.y1, 0.2, "y1 must be vertical coordinate");
  assert.strictEqual(norm.x2, 0.3, "x2 must be horizontal coordinate");
  assert.strictEqual(norm.y2, 0.4, "y2 must be vertical coordinate");
  console.log("✔ Test 5: Normalized coordinate axis orientation [x1, y1, x2, y2] PASS");
}

console.log("\nALL BOUNDING BOX GEOMETRY TESTS PASSED SUCCESSFULLY!");
