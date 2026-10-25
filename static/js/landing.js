/**
 * landing.js — CrimeVision AI Landing Page Interactions & 3D Spatial Canvas
 */

"use strict";

document.addEventListener("DOMContentLoaded", () => {
  // 1. Smooth Scrolling for all anchor links
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener("click", function(e) {
      const targetId = this.getAttribute("href");
      if (targetId && targetId !== "#") {
        const target = document.querySelector(targetId);
        if (target) {
          e.preventDefault();
          target.scrollIntoView({ behavior: "smooth" });
        }
      }
    });
  });

  // 2. Interactive 3D Spatial Canvas in Spatial Section
  initLandingThreeCanvas();
});

function initLandingThreeCanvas() {
  const canvas = document.getElementById("landing-three-canvas");
  if (!canvas || typeof THREE === "undefined") return;

  const parent = canvas.parentElement;
  const width = parent.clientWidth || 600;
  const height = parent.clientHeight || 460;

  // Scene
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x04060B);
  scene.fog = new THREE.FogExp2(0x04060B, 0.025);

  // Camera
  const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 500);
  camera.position.set(0, 10, 16);

  // Renderer
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setSize(width, height);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

  // Controls
  let controls = null;
  if (typeof THREE.OrbitControls !== "undefined") {
    controls = new THREE.OrbitControls(camera, canvas);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.8;
    controls.maxPolarAngle = Math.PI / 2 - 0.05;
  }

  // Ground Grid
  const grid = new THREE.GridHelper(24, 24, 0x00F0FF, 0x1E293B);
  scene.add(grid);

  // Ambient & Directional Lights
  const ambLight = new THREE.AmbientLight(0xffffff, 0.7);
  scene.add(ambLight);

  const dirLight = new THREE.DirectionalLight(0x00F0FF, 0.8);
  dirLight.position.set(10, 20, 10);
  scene.add(dirLight);

  // Sample Forensic 3D Bounding Boxes
  const objectsGroup = new THREE.Group();
  scene.add(objectsGroup);

  const sampleBoxes = [
    { pos: [-3, 1, 2], dim: [1.2, 2.0, 1.2], col: 0x38BDF8 }, // Person
    { pos: [3.5, 0.9, -2], dim: [2.2, 1.8, 4.2], col: 0x818CF8 }, // Vehicle
    { pos: [-1.5, 0.4, -3], dim: [0.8, 0.8, 0.8], col: 0xF59E0B }, // Bag
    { pos: [1.2, 0.8, 3.5], dim: [1.0, 1.6, 1.0], col: 0x38BDF8 }, // Person
  ];

  sampleBoxes.forEach(item => {
    const geo = new THREE.BoxGeometry(item.dim[0], item.dim[1], item.dim[2]);
    const mat = new THREE.MeshStandardMaterial({
      color: item.col,
      roughness: 0.3,
      metalness: 0.2,
      transparent: true,
      opacity: 0.85,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(item.pos[0], item.pos[1], item.pos[2]);

    const wireMat = new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.4 });
    const wireGeo = new THREE.WireframeGeometry(geo);
    const line = new THREE.LineSegments(wireGeo, wireMat);
    mesh.add(line);

    objectsGroup.add(mesh);
  });

  // IntersectionObserver to pause loop when off-screen
  let isPaused = false;
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        isPaused = !entry.isIntersecting;
      });
    }, { threshold: 0.05 });
    observer.observe(parent);
  }

  // Animation Loop
  function animate() {
    requestAnimationFrame(animate);
    if (isPaused) return;
    if (controls) controls.update();
    renderer.render(scene, camera);
  }
  animate();

  // Resize listener
  window.addEventListener("resize", () => {
    if (!parent || !renderer || !camera) return;
    const w = parent.clientWidth;
    const h = parent.clientHeight;
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    renderer.setSize(w, h);
  });
}
