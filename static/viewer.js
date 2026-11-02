// 3D-Anzeige des Partners: Modelle aus Next Order (FBX + eigene Animations-/Augen-Daten), Toon-Look,
// Rollen-Animationen und Digitations-Sequenz. Nutzt three.js über die Importmap in index.html.
import * as THREE from "three";
import { FBXLoader } from "three/addons/loaders/FBXLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { OBJLoader } from "three/addons/loaders/OBJLoader.js";
import { World } from "/static/world.js";

// Rolle -> Animationsname im Spiel (erste passende gewinnt). Die Gefühle wurden an Agumon und Gabumon angesehen:
// feel_fa Jubel (Arme hoch) · fb Winken · fc gekrümmt, Hand am Bauch · fd kleine Freude · fe Kopf kratzen/schief ·
// fg Sprung vor Freude · fh Kopf hängen lassen · fi Gähnen. feel_ff ist uneinheitlich (wütend bzw. Sprung) und bleibt ungenutzt.
const ROLES = {
  idle: [/_base_fa0/], idle2: [/_base_fb0/], eat: [/_eat_/], sleep: [/_rest_/], walk: [/_walk_fa0/], run: [/_run_/],
  // Jubel und Winken haben nur 27 von 88 Modellen – sonst Freudensprung bzw. kleine Freude
  happy: [/_feel_fd0/, /_jump_fa1/], cheer: [/_feel_fa0/, /_feel_fg0/, /_jump_fa1/], greet: [/_feel_fb0/, /_feel_fd0/],
  hungry: [/_feel_fc0/], sad: [/_feel_fc0/], down: [/_feel_fh0/], confused: [/_feel_fe0/], tired: [/_feel_fi0/],
  train: [/_atck_fa0/], special: [/_spat_/], getup: [/_getu_/],
};
const ONCE = new Set(["eat", "happy", "cheer", "greet", "down", "confused", "tired", "train", "special", "getup"]);
// Jubel ist kurz: zweimal hintereinander, der halbsekündige Freudensprung dreimal
const repeatsFor = (role, clip) => (role !== "cheer" ? 1 : /_jump_/.test(clip) ? 3 : 2);
// Augen-Textur in vier Vierteln (siehe _toon): offen, böse, zu, fröhlich
const EYES = { open: [0, 0.5], angry: [0.5, 0.5], closed: [0, 0], happy: [0.5, 0] };
const ROLE_EYES = { happy: "happy", cheer: "happy", greet: "happy", sleep: "closed", tired: "closed", down: "closed" };

const tex = (loader, url, srgb = true) => new Promise((ok) => loader.load(url, (t) => { if (srgb) t.colorSpace = THREE.SRGBColorSpace; ok(t); }, undefined, () => ok(null)));
const json = (url) => fetch(url).then((r) => (r.ok ? r.json() : null)).catch(() => null);
const wait = (ms) => new Promise((ok) => setTimeout(ok, ms));
const hidden = new THREE.MeshBasicMaterial({ visible: false });

export class Viewer {
  /** plain: nur Modell, ohne Boden/Himmel/Steuerung und ohne Dauer-Schleife (für Einzelbilder). */
  constructor(el, { plain = false } = {}) {
    this.el = el; this.plain = plain;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    el.prepend(this.renderer.domElement);
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(32, 1, 0.01, 200);
    this.hemi = new THREE.HemisphereLight("#ffffff", "#5577aa", 1.6);
    this.sun = new THREE.DirectionalLight("#ffffff", 2.2);
    this.sun.position.set(2, 4, 3);
    this.scene.add(this.hemi, this.sun);
    this.tex = new THREE.TextureLoader();
    this.cache = new Map();
    this.eyeOffset = { value: new THREE.Vector2(0, 0.5) };
    this.model = null; this.mixer = null; this.actions = {}; this.playing = null; this.role = null; this.token = 0;
    this.clock = new THREE.Clock();
    if (plain) { this.resize(); return; }
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.controls.enablePan = false;
    this.floor = this._floor();
    this.scene.add(this.floor);
    addEventListener("resize", () => this.resize());
    this.resize();
    this.renderer.setAnimationLoop(() => this._frame());
  }

  dispose() {
    this.renderer.setAnimationLoop(null);
    this.controls?.dispose();
    this.renderer.dispose();
    this.renderer.forceContextLoss();
    this.renderer.domElement.remove();
  }

  _floor() {
    const g = new THREE.Group();
    const disc = new THREE.Mesh(new THREE.CircleGeometry(30, 64), new THREE.MeshBasicMaterial({ color: "#e9f1f5" }));
    disc.rotation.x = -Math.PI / 2;
    this.pad = new THREE.Mesh(new THREE.RingGeometry(0.55, 0.6, 64), new THREE.MeshBasicMaterial({ color: "#9fc3d3" }));
    this.pad.rotation.x = -Math.PI / 2; this.pad.position.y = 0.003;
    // Sonne bzw. Mond: flache Scheibe weit hinten im Himmel, die Sonne mit sich langsam drehendem Strahlenkranz
    this.orb = new THREE.Mesh(new THREE.CircleGeometry(1, 48), new THREE.MeshBasicMaterial({ color: "#fff3c4", fog: false }));
    const ray = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-0.13, 1.25, 0), new THREE.Vector3(0.13, 1.25, 0), new THREE.Vector3(0, 1.75, 0)]);
    this.rays = new THREE.Group();
    this.rayMat = new THREE.MeshBasicMaterial({ color: "#ffe98a", fog: false, side: THREE.DoubleSide });
    for (let i = 0; i < 12; i++) { const r = new THREE.Mesh(ray, this.rayMat); r.rotation.z = (i / 12) * Math.PI * 2; this.rays.add(r); }
    this.rays.position.z = -0.01;
    this.orb.add(this.rays);
    this.world = new World();
    this.disc = disc;
    g.add(disc, this.pad, this.world.group);
    this.scene.add(this.orb);
    this.scene.fog = new THREE.Fog("#a9d8f0", 10, 40);
    this.setTime("day");
    return g;
  }

  resize() {
    const w = this.el.clientWidth, h = this.el.clientHeight;
    this.renderer.setSize(w, h); this.camera.aspect = w / h; this.camera.updateProjectionMatrix();
  }

  /** Tageszeit der Welt: flache Farben für Himmel, Boden, Gitter und Sonne/Mond. */
  setTime(time) {
    // Digitale Welt: kräftige, flache Farben (kein Verlauf), Gitterboden wie im Anime
    const T = {
      day:   { sky: "#3fb0f2", pad: "#ffffff", orb: "#fff4b8", hemi: 1.6, sun: 2.2 },
      dusk:  { sky: "#ff8f5e", pad: "#ffffff", orb: "#ffe8a3", hemi: 1.3, sun: 1.8 },
      night: { sky: "#0a1330", pad: "#5d86d6", orb: "#e8eef7", hemi: 0.7, sun: 0.8 },
    }[time] || {};
    if (!T.sky || !this.disc) return;
    this.scene.background = new THREE.Color(T.sky);
    this.scene.fog.color.set(T.sky);
    // Boden-Bild (Wiesen, Pfad, Platz) je Tageszeit neu malen, aber nur beim Wechsel
    if (this._time !== time) {
      this.disc.material.map = this.world.floorMap(time); this.disc.material.color.set("#ffffff");
      this.disc.material.needsUpdate = true; this._time = time;
    }
    this.pad.material.color.set(T.pad);
    this.orb.material.color.set(T.orb);
    this.orb.userData.night = time === "night";
    this.rays.visible = time !== "night";
    this.rayMat.color.set(time === "dusk" ? "#ffd27a" : "#ffe98a");
    this.world.setTime(time);
    this.hemi.intensity = T.hemi; this.sun.intensity = T.sun;
    this._placeOrb();
  }

  _placeOrb() {
    const s = this.view || 1;
    const night = this.orb.userData.night;
    this.orb.position.set(-s * 9, s * (night ? 3.9 : 4.2), -s * 18);
    this.orb.scale.setScalar(s * (night ? 0.55 : 0.7));
    if (this.scene.fog) { this.scene.fog.near = s * 6; this.scene.fog.far = s * 26; }
  }

  setEyes(x, y) { this.eyeOffset.value.set(x, y); }

  // --- Laden ------------------------------------------------------------------------------
  _toon(map, ramp, eye) {
    const mat = new THREE.MeshToonMaterial({ map, gradientMap: ramp || undefined });
    if (!eye) return mat;
    const eyeOffset = this.eyeOffset;
    mat.onBeforeCompile = (sh) => {
      sh.uniforms.eyeTex = { value: eye };
      sh.uniforms.eyeOffset = eyeOffset;
      sh.vertexShader = sh.vertexShader
        .replace("#include <common>", "#include <common>\nattribute vec3 eyeUv;\nvarying vec3 vEyeUv;")
        .replace("#include <uv_vertex>", "#include <uv_vertex>\nvEyeUv = eyeUv;");
      sh.fragmentShader = sh.fragmentShader
        .replace("#include <common>", "#include <common>\nuniform sampler2D eyeTex;\nuniform vec2 eyeOffset;\nvarying vec3 vEyeUv;")
        .replace("#include <map_fragment>", `#include <map_fragment>
          if (vEyeUv.z > 0.5) {
            vec4 e = texture2D(eyeTex, clamp(vEyeUv.xy, 0.004, 0.996) * 0.5 + eyeOffset);
            diffuseColor.rgb = mix(diffuseColor.rgb, e.rgb, e.a);
          }`);
    };
    return mat;
  }

  /** Augen-UV je Dreieck zuordnen (Erklärung in werkzeuge/uv_export.py). */
  _eyeUv(geo, uvs) {
    const G = 1000, ck = (u, v) => `${Math.round(u * G)},${Math.round(v * G)}`;
    const table = new Map();
    for (let t = 0; t < uvs.eye.length; t++) {
      const corners = [0, 1, 2].map((c) => { const o = (t * 3 + c) * 4; return { key: ck(uvs.tris[o], uvs.tris[o + 1]), uv1: [uvs.tris[o + 2], uvs.tris[o + 3]] }; });
      const key = corners.map((c) => c.key).sort().join("|");
      if (!table.has(key)) table.set(key, { corners, eye: uvs.eye[t] });
    }
    const uv = geo.attributes.uv; if (!uv) return 0;
    const n = uv.count, idx = geo.index ? (i) => geo.index.getX(i) : (i) => i, tri = geo.index ? geo.index.count : n;
    const run = (flip) => {
      const out = new Float32Array(n * 3); let hits = 0;
      for (let t = 0; t < tri; t += 3) {
        const ids = [idx(t), idx(t + 1), idx(t + 2)];
        const keys = ids.map((i) => ck(uv.getX(i), flip ? 1 - uv.getY(i) : uv.getY(i)));
        const hit = table.get([...keys].sort().join("|"));
        if (!hit) continue;
        hits++;
        ids.forEach((i, c) => { const k = hit.corners.find((x) => x.key === keys[c]) || hit.corners[c]; out.set([k.uv1[0], k.uv1[1], hit.eye], i * 3); });
      }
      return { out, hits };
    };
    const a = run(false), b = run(true), best = a.hits >= b.hits ? a : b;
    geo.setAttribute("eyeUv", new THREE.BufferAttribute(best.out, 3));
    return best.hits;
  }

  async _load(id) {
    if (this.cache.has(id)) return this.cache.get(id);
    const dir = `/assets/${id}/`;
    // FBXLoader liefert das Modell, bevor seine Körpertexturen fertig sind.
    // Einzelbilder werden nur einmal gerendert: ohne diese Schranke bleiben sie schwarz.
    // Pro Ladevorgang ein eigener Manager, damit andere Viewer nicht dazwischenfunken.
    const manager = new THREE.LoadingManager();
    const texturesReady = new Promise((resolve) => { manager.onLoad = resolve; });
    const fbx = await new FBXLoader(manager).loadAsync(dir + `${id}.fbx`).catch(() => null);
    if (!fbx) return null;
    await texturesReady;
    const [anims, uvs, ramp, eye] = await Promise.all([json(dir + "anim.json"), json(dir + "uv.json"),
      tex(this.tex, dir + `${id}_r00.png`, false), tex(this.tex, dir + `${id}_e00.png`)]);
    if (ramp) { ramp.minFilter = ramp.magFilter = THREE.NearestFilter; ramp.generateMipmaps = false; }
    if (eye) { eye.generateMipmaps = false; eye.minFilter = THREE.LinearFilter; }
    fbx.traverse((o) => {
      if (!o.isMesh) return;
      o.frustumCulled = false;
      const hasEye = eye && uvs && uvs.eye.length && this._eyeUv(o.geometry, uvs) > 0;
      // Körper = <id>_cNN; andere Materialien sind Effekt-Auren, die nur bei Angriffen leuchten
      const conv = (mt) => (/_c\d\d$/.test(mt.name || "") || !mt.map ? this._toon(mt.map || null, ramp, hasEye ? eye : null) : hidden);
      o.material = Array.isArray(o.material) ? o.material.map(conv) : conv(o.material);
      if ([].concat(o.material).every((mt) => mt === hidden)) o.visible = false;
    });
    const entry = { root: fbx, clips: anims?.clips || [] };
    this.cache.set(id, entry);
    return entry;
  }

  /** Digi-Ei aus Next Order (unbewegtes OBJ-Modell + Muster-Textur); wackelt per Code. */
  async _egg(model) {
    const key = "egg:" + model;
    if (this.cache.has(key)) return this.cache.get(key);
    const dir = `/assets/${model}/`;
    const obj = await new OBJLoader().loadAsync(dir + `${model}.obj`).catch(() => null);
    if (!obj) return null;
    const [map, ramp] = await Promise.all([tex(this.tex, dir + `${model}.png`), tex(this.tex, dir + `${model}_r00.png`, false)]);
    if (ramp) { ramp.minFilter = ramp.magFilter = THREE.NearestFilter; ramp.generateMipmaps = false; }
    obj.traverse((o) => { if (o.isMesh) o.material = new THREE.MeshToonMaterial({ map, gradientMap: ramp || undefined }); });
    const root = new THREE.Group(); root.add(obj);
    const entry = { root, clips: [], egg: true };
    this.cache.set(key, entry);
    return entry;
  }

  _buildActions(entry) {
    const bones = {};
    entry.root.traverse((o) => { if (o.isBone || o.type === "Object3D") bones[o.name] = o; });
    const ratios = [];
    for (const c of entry.clips) for (const t of c.tracks) {
      const b = bones[t.bone];
      if (t.type !== "position" || !b) continue;
      const l = Math.hypot(t.values[0], t.values[1], t.values[2]);
      if (l > 1e-4 && b.position.length() > 1e-4) ratios.push(b.position.length() / l);
    }
    ratios.sort((a, b) => a - b);
    const scale = ratios.length ? ratios[ratios.length >> 1] : 1;
    const mixer = new THREE.AnimationMixer(entry.root), actions = {};
    for (const c of entry.clips) {
      const n = Math.round(c.duration * c.fps) + 1, times = Array.from({ length: n }, (_, i) => i / c.fps);
      const tracks = [];
      for (const t of c.tracks) {
        if (!bones[t.bone]) continue;
        const name = THREE.PropertyBinding.sanitizeNodeName(t.bone);
        const size = t.type === "quaternion" ? 4 : 3;
        const constant = t.values.length === size;           // unveränderliche Spur: nur ein Wert gespeichert
        const tt = constant ? [0] : times;
        const vals = t.type === "position" ? t.values.map((v) => v * scale) : t.values;
        if (t.type === "quaternion") tracks.push(new THREE.QuaternionKeyframeTrack(`${name}.quaternion`, tt, vals));
        else if (t.type === "position") tracks.push(new THREE.VectorKeyframeTrack(`${name}.position`, tt, vals));
        else tracks.push(new THREE.VectorKeyframeTrack(`${name}.scale`, tt, vals));
      }
      if (tracks.length) actions[c.name] = mixer.clipAction(new THREE.AnimationClip(c.name, c.duration, tracks));
    }
    return { mixer, actions };
  }

  _frameCamera() {
    const root = this.model;
    root.updateMatrixWorld(true);
    const box = new THREE.Box3();
    root.traverse((o) => { if (o.isMesh && o.visible) box.expandByObject(o, true); });
    const size = box.getSize(new THREE.Vector3()), c = box.getCenter(new THREE.Vector3());
    root.position.y -= box.min.y;
    const h = Math.max(size.y, size.x * 0.7, size.z * 0.7);
    // Babys sollen klein wirken, Megas groß: die Kamera nimmt mindestens Rookie-Größe an
    // und wächst darüber nur gebremst mit (Größen im Spiel: Baby ~0.35, Rookie ~0.9, Champion ~2.2, Mega ~3)
    if (this.plain) {
      // Einzelbild: Modell füllt das Bild, Blick leicht schräg von vorn
      const r = Math.max(size.y, size.x, size.z) * 0.5;
      const d = r / Math.tan((this.camera.fov / 2) * Math.PI / 180) * 1.25;
      const cy = size.y / 2;
      this.camera.position.set(c.x + d * 0.35, cy + d * 0.08, c.z + d * 0.94);
      this.camera.lookAt(c.x, cy, c.z);
      this.camera.near = d / 100; this.camera.far = d * 10; this.camera.updateProjectionMatrix();
      this.size = h; this.view = h;
      return;
    }
    const MIN = 0.9, hv = h < MIN ? MIN : MIN + (h - MIN) * 0.8;
    this.floor.scale.setScalar(hv / 1.3);
    this.pad.scale.setScalar(Math.max(size.x, size.z, h * 0.6) / hv * 1.3);
    this.controls.target.set(c.x, Math.max(size.y * 0.42, hv * 0.28), c.z);
    this.camera.position.set(c.x + hv * 1.1, Math.max(size.y * 0.55, hv * 0.4) + hv * 0.25, c.z + hv * 2.9);
    this.camera.near = hv / 100; this.camera.far = hv * 80; this.camera.updateProjectionMatrix();
    this.size = h; this.view = hv;
    this._placeOrb();
  }

  /** Form anzeigen ("egg" = Digi-Ei, eggModel z. B. "egg01"). Gibt false zurück, wenn das Modell fehlt. */
  async show(id, eggModel) {
    const token = ++this.token;
    const entry = id === "egg" ? await this._egg(eggModel || "egg01") : await this._load(id);
    if (token !== this.token) return true;
    if (!entry) return false;
    if (this.model) this.scene.remove(this.model);
    this.mixer?.stopAllAction();
    this.model = entry.root;
    this.model.position.set(0, 0, 0); this.model.rotation.set(0, 0, 0); this.model.scale.setScalar(1);
    this.id = id;
    ({ mixer: this.mixer, actions: this.actions } = entry.egg ? { mixer: null, actions: {} } : this._buildActions(entry));
    this.scene.add(this.model);
    this.playing = null; this.role = null;
    this.play("idle", true);
    this.mixer?.update(0.01);
    this._frameCamera();
    return true;
  }

  clipFor(role) {
    const names = Object.keys(this.actions);
    for (const re of ROLES[role] || []) { const n = names.find((x) => re.test(x)); if (n) return n; }
    return null;
  }

  /** Rolle abspielen. Einmal-Animationen (Essen, Freude …) kehren danach zur Grundrolle zurück. */
  play(role, force = false) {
    if (!force && role === this.role && !ONCE.has(role)) return;
    const name = this.clipFor(role) || this.clipFor("idle");
    const next = name && this.actions[name];
    this.role = role;
    const eyes = EYES[ROLE_EYES[role] || "open"];
    this.setEyes(eyes[0], eyes[1]);
    if (!next) return;
    next.reset();
    if (ONCE.has(role)) {
      const times = repeatsFor(role, name);
      next.setLoop(times > 1 ? THREE.LoopRepeat : THREE.LoopOnce, times); next.clampWhenFinished = true;
      clearTimeout(this._back);
      this._back = setTimeout(() => this.play(this.baseRole || "idle", true), next.getClip().duration * times * 1000 - 120);
    } else {
      next.setLoop(THREE.LoopRepeat);
      this.baseRole = role;
    }
    next.play();
    if (this.playing && this.playing !== next) this.playing.crossFadeTo(next, 0.25, false);
    this.playing = next;
  }

  /** Grundrolle (z. B. "sleep" nachts, "hungry" bei leerem Magen) – Einmal-Animationen laufen zu Ende. */
  setBase(role) {
    this.baseRole = role;
    if (!this.playing || !ONCE.has(this.role)) this.play(role);
  }

  // --- Digitation -------------------------------------------------------------------------
  _white(on) {
    this.model?.traverse((o) => {
      if (!o.isMesh || !o.visible) return;
      if (on) { o.userData.mat = o.material; o.material = new THREE.MeshBasicMaterial({ color: "#ffffff" }); }
      else if (o.userData.mat) { o.material = o.userData.mat; delete o.userData.mat; }
    });
  }

  _ring() {
    const r = new THREE.Mesh(new THREE.RingGeometry(0.9, 1, 64), new THREE.MeshBasicMaterial({ color: "#ffffff", transparent: true, side: THREE.DoubleSide, fog: false }));
    r.position.set(0, this.size * 0.45, 0);
    r.scale.setScalar(this.size * 0.2);
    this.scene.add(r);
    const start = performance.now();
    const grow = () => {
      const k = (performance.now() - start) / 1100;
      r.scale.setScalar(this.size * (0.2 + k * 1.4));
      r.material.opacity = Math.max(0, 1 - k);
      r.lookAt(this.camera.position);
      if (k < 1) requestAnimationFrame(grow); else { this.scene.remove(r); r.geometry.dispose(); }
    };
    grow();
  }

  /** Sequenz: weiß leuchten, drehen, Ringe, Blitz, neue Form erscheint weiß und bekommt Farbe. */
  async digivolve(toId, line, { onFlash } = {}) {
    this._white(true);
    this.spinning = true;
    for (let i = 0; i < 4; i++) { this._ring(); await wait(320); }
    onFlash?.();
    await wait(120);
    this.spinning = false;
    await this.show(toId, line);
    this._white(true);
    this.spinning = true;
    this._ring(); this._ring();
    await wait(700);
    this.spinning = false;
    this.model.rotation.y = 0;
    await wait(200);
    this._white(false);
    this.play("cheer", true);
  }

  /** Wo steht der Kopf gerade auf dem Bildschirm? (0–1, für die Sprechblase) */
  headPoint() {
    if (!this.model || !this.size) return null;
    const p = new THREE.Vector3(0, this.size * 1.02, 0).project(this.camera);
    return { x: (p.x + 1) / 2, y: (1 - p.y) / 2 };
  }

  _frame() {
    const dt = Math.min(0.1, this.clock.getDelta());
    this.mixer?.update(dt);
    if (this.world) { this.world.update(dt); this.rays.rotation.z -= dt * 0.15; }
    if (this.spinning && this.model) this.model.rotation.y += dt * 9;
    else if (this.id === "egg" && this.model) {
      // Ei wackelt: ruhig hin und her, ab und zu ein kleiner Hüpfer
      const t = performance.now() / 1000;
      this.model.rotation.z = Math.sin(t * 2.2) * 0.06 * (1 + Math.max(0, Math.sin(t * 0.7)) * 1.5);
    }
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
  }
}

/** Farbiges Standbild einer Form oder eines Eis (für Team und Ei-Auswahl) als PNG-Daten-URL, oder null.
 *  Ein gemeinsamer unsichtbarer Viewer arbeitet die Bilder nacheinander ab (nur ein WebGL-Kontext). */
let shotViewer = null, shotQueue = Promise.resolve();
export function snapshot(id, eggModel, px = 240) {
  const job = shotQueue.then(async () => {
    if (!shotViewer) {
      const el = document.createElement("div");
      el.style.cssText = `position:fixed;left:-10000px;top:0;width:${px}px;height:${px}px;pointer-events:none`;
      document.body.append(el);
      shotViewer = new Viewer(el, { plain: true });
    }
    const v = shotViewer;
    if (!(await v.show(id, eggModel))) return null;
    v.mixer?.update(0.4);
    v._frameCamera();
    v.renderer.render(v.scene, v.camera);
    return v.renderer.domElement.toDataURL("image/png");
  }).catch(() => null);
  shotQueue = job;
  return job;
}

/** Schatten-Bild einer Form ("Wer ist das?"): schwarze Silhouette als PNG-Daten-URL, oder null. */
export async function silhouette(id, px = 320) {
  const el = document.createElement("div");
  el.style.cssText = `position:fixed;left:-10000px;top:0;width:${px}px;height:${px}px;pointer-events:none`;
  document.body.append(el);
  const v = new Viewer(el, { plain: true });
  try {
    if (!(await v.show(id))) return null;
    v.mixer?.update(0.4);
    const black = new THREE.MeshBasicMaterial({ color: "#000000" });
    v.model.traverse((o) => {
      if (o.isMesh && o.visible) o.material = Array.isArray(o.material) ? o.material.map((m) => (m === hidden ? m : black)) : black;
    });
    v._frameCamera();
    v.renderer.render(v.scene, v.camera);
    return v.renderer.domElement.toDataURL("image/png");
  } catch { return null; } finally { v.dispose(); el.remove(); }
}
