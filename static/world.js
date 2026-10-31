// Die Digitale Welt rund um den Partner: Berge am Horizont, Bäume, Felsen und Kristalle auf dem Gitter,
// schwebende Inseln und Daten-Würfel, ziehende Wolken, Datenregen in der Ferne, aufsteigende Datenpunkte, Sterne.
// Flacher Anime-Look (Toon-Schattierung, keine Verläufe). Alles liegt in einer Gruppe, die mit dem Boden mitskaliert
// (Einheiten = Boden-Einheiten, der Partner steht in der Mitte). Wird per Zufall mit festem Startwert erzeugt,
// damit die Welt bei jedem Besuch gleich aussieht.
import * as THREE from "three";

function rng(seed) {
  return () => { seed |= 0; seed = (seed + 0x6d2b79f5) | 0; let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

// Farben je Tageszeit
export const PALETTE = {
  day:   { floor: "#c4ebff", grid: "#7cc9f2", tile: "#8fd3fa", meadow: "#a6e6b3", meadow2: "#86d79b", path: "#f6e6bd", pathEdge: "#e3cd97", plaza: "#eaf8ff", plazaEdge: "#8fd3fa", circuit: "#93d4f7", pebble: "#a9c2d6", flowers: ["#ffffff", "#ffe066", "#ff8fb8"],
           far: "#8fd0f7", near: "#62b6ec", leaf: "#3cc46e", trunk: "#9b6b47", rock: "#a9c2d6", crystal: "#7ff0ff",
           cube: "#ffffff", cloud: "#ffffff", rain: "#ffffff", grass: "#58c977", isle: "#8aa7bd", mote: "#ffffff", stars: 0 },
  dusk:  { floor: "#ffd6bf", grid: "#f5a77f", tile: "#ffb48e", meadow: "#dcd3a0", meadow2: "#c8bd86", path: "#ffe9d2", pathEdge: "#f2c9a6", plaza: "#fff0e6", plazaEdge: "#ffb48e", circuit: "#f8b697", pebble: "#c9a196", flowers: ["#fff4ea", "#ffd466", "#ff9db0"],
           far: "#f4ae8e", near: "#e48a77", leaf: "#58a565", trunk: "#7d4e38", rock: "#c9a196", crystal: "#ffd6ae",
           cube: "#fff1e6", cloud: "#ffd9c8", rain: "#fff3ea", grass: "#72ad6b", isle: "#b98e85", mote: "#fff4d6", stars: 0.3 },
  night: { floor: "#13214a", grid: "#2b4d94", tile: "#2a52a8", meadow: "#163b52", meadow2: "#1a4659", path: "#26345f", pathEdge: "#2e3e70", plaza: "#1b2c5e", plazaEdge: "#3f6fd1", circuit: "#2c56b0", pebble: "#34477c", flowers: ["#9fb8e8", "#8fa6d6", "#a88fd0"],
           far: "#16244d", near: "#1d3164", leaf: "#1f5f5f", trunk: "#2b2f4f", rock: "#34477c", crystal: "#5ee0ff",
           cube: "#8fb4ff", cloud: "#22356a", rain: "#7fd4ff", grass: "#25596a", isle: "#2c3a66", mote: "#9fe3ff", stars: 1 },
};

export class World {
  constructor() {
    this.group = new THREE.Group();
    this.rand = rng(20261031);
    this.t = 0;
    // Toon-Rampe mit drei harten Stufen (Anime-Schatten)
    const ramp = new THREE.DataTexture(new Uint8Array([90, 170, 255]), 3, 1, THREE.RedFormat);
    ramp.minFilter = ramp.magFilter = THREE.NearestFilter; ramp.needsUpdate = true;
    const toon = (extra = {}) => new THREE.MeshToonMaterial({ gradientMap: ramp, ...extra });
    this.mat = {
      far: new THREE.MeshBasicMaterial({ fog: false }), near: new THREE.MeshBasicMaterial({ fog: false }),
      leaf: toon({ flatShading: true }), trunk: toon(), rock: toon({ flatShading: true }), crystal: toon({ flatShading: true }),
      cube: toon(), cloud: new THREE.MeshBasicMaterial({ fog: false }), tile: new THREE.MeshBasicMaterial(), grass: toon({ flatShading: true }), isle: toon({ flatShading: true }),
      rain: new THREE.MeshBasicMaterial({ transparent: true, opacity: 0.55 }),
      mote: new THREE.PointsMaterial({ size: 0.07, transparent: true, opacity: 0.85 }),
      stars: new THREE.PointsMaterial({ size: 1.6, sizeAttenuation: false, transparent: true, fog: false, color: "#ffffff" }),
    };
    this._floorLayout();
    this._mountains();
    this._tiles();
    this._flowers();
    this._trees();
    this._rocks();
    this._crystals();
    this._islands();
    this._cubes();
    this._clouds();
    this._rain();
    this._motes();
    this._stars();
  }

  /** Punkt auf einem Ring um die Mitte (Winkel zufällig) */
  _ring(min, max) {
    const a = this.rand() * Math.PI * 2, r = min + this.rand() * (max - min);
    return [Math.cos(a) * r, Math.sin(a) * r, a];
  }

  _instanced(geo, mat, n, place) {
    const mesh = new THREE.InstancedMesh(geo, mat, n), d = new THREE.Object3D();
    for (let i = 0; i < n; i++) { place(d, i); d.updateMatrix(); mesh.setMatrixAt(i, d.matrix); }
    mesh.frustumCulled = false;
    this.group.add(mesh);
    return mesh;
  }

  // Zwei Reihen kantiger Berge als flache Silhouetten am Horizont
  _mountains() {
    const geo = new THREE.ConeGeometry(1, 1, 5, 1);
    geo.translate(0, 0.5, 0);
    for (const [key, n, rMin, rMax, hMin, hMax] of [["far", 30, 40, 44, 2.6, 4.6], ["near", 26, 32, 35, 1.4, 2.8]]) {
      this._instanced(geo, this.mat[key], n, (d, i) => {
        const a = (i / n) * Math.PI * 2 + this.rand() * 0.2, r = rMin + this.rand() * (rMax - rMin), h = hMin + this.rand() * (hMax - hMin);
        d.position.set(Math.cos(a) * r, -0.2, Math.sin(a) * r);
        d.scale.set(h * (0.8 + this.rand() * 0.6), h, h * 0.8);
        d.rotation.y = this.rand() * Math.PI;
      });
    }
  }

  // --- Boden ---------------------------------------------------------------------------------
  /** Lage von Wiesen, Pfad, Platz und Datenleitungen (einmal ausgewürfelt, beim Färben nur neu gemalt) */
  _floorLayout() {
    const R = rng(4242);
    // Wiesen: je ein paar überlappende Kreise; einige nah an der Kamera, damit der Vordergrund nicht leer ist
    this.patches = [];
    for (let i = 0; i < 46; i++) {
      const a = R() * Math.PI * 2, r = i < 10 ? 2.6 + R() * 4 : 4 + R() * 24, x = Math.cos(a) * r, z = Math.sin(a) * r;
      const size = 0.9 + R() * (r / 10 + 1.2), parts = 3 + Math.floor(R() * 4), shade = R() < 0.5;
      const circles = Array.from({ length: parts }, () => [x + (R() - 0.5) * size * 1.6, z + (R() - 0.5) * size * 1.2, size * (0.5 + R() * 0.5)]);
      this.patches.push({ circles, shade });
    }
    // Pfad: vom Platz in Blickrichtung (nach hinten links) zum Horizont, leicht geschwungen
    this.path = [];
    for (let k = 0; k <= 60; k++) {
      const t = k / 60, d = 1.0 + t * 30;
      const a = -2.0 + Math.sin(t * 5.5) * 0.18 + t * 0.25;
      this.path.push([Math.cos(a) * d, Math.sin(a) * d]);
    }
    // Datenleitungen: vom Platz aus nach außen, nur in 45°-Schritten, am Ende ein Punkt
    this.circuits = [];
    for (let i = 0; i < 16; i++) {
      let a = Math.round((R() * Math.PI * 2) / (Math.PI / 4)) * (Math.PI / 4), x = Math.cos(a) * 1.08, z = Math.sin(a) * 1.08;
      const pts = [[x, z]];
      for (let seg = 0; seg < 2 + Math.floor(R() * 3); seg++) {
        const len = 1 + R() * 3.5;
        x += Math.cos(a) * len; z += Math.sin(a) * len; pts.push([x, z]);
        a += (R() < 0.5 ? -1 : 1) * Math.PI / 4;
      }
      this.circuits.push(pts);
    }
    this.pebbles = Array.from({ length: 160 }, () => { const a = R() * Math.PI * 2, r = 2 + R() * 22; return [Math.cos(a) * r, Math.sin(a) * r, 0.05 + R() * 0.08]; });
  }

  _inMeadow(x, z, pad = 0) { return this.patches.some((p) => p.circles.some(([cx, cz, r]) => (x - cx) ** 2 + (z - cz) ** 2 < (r + pad) ** 2)); }
  _onPath(x, z, pad = 0) { return this.path.some(([px, pz]) => (x - px) ** 2 + (z - pz) ** 2 < (0.85 + pad) ** 2); }
  /** Freier Gitterboden (für die leuchtenden Datenfelder) */
  _bare(x, z) { return Math.hypot(x, z) > 1.6 && !this._inMeadow(x, z, 0.7) && !this._onPath(x, z, 0.7); }

  /** Boden-Bild für die Tageszeit malen (Mitte des Bildes = Mitte der Welt, 60 Einheiten breit) */
  floorMap(time) {
    const P = PALETTE[time] || PALETTE.day, S = 2048, U = S / 60;
    this.canvas ||= Object.assign(document.createElement("canvas"), { width: S, height: S });
    const g = this.canvas.getContext("2d"), X = (v) => (v + 30) * U;
    g.fillStyle = P.floor; g.fillRect(0, 0, S, S);
    // Raster (eine Zelle = eine Einheit); Wiesen, Weg und Platz werden danach darübergemalt,
    // so bleibt das Gitter nur auf dem freien digitalen Boden sichtbar
    g.fillStyle = P.grid;
    const line = Math.max(2, 0.05 * U);
    for (let k = 0; k <= 60; k++) { const q = k * U - line / 2; g.fillRect(q, 0, line, S); g.fillRect(0, q, S, line); }
    g.lineCap = g.lineJoin = "round";
    // Datenleitungen
    g.strokeStyle = g.fillStyle = P.circuit; g.lineWidth = 0.09 * U;
    for (const pts of this.circuits) {
      g.beginPath(); pts.forEach(([x, z], i) => (i ? g.lineTo(X(x), X(z)) : g.moveTo(X(x), X(z)))); g.stroke();
      const [ex, ez] = pts[pts.length - 1];
      g.beginPath(); g.arc(X(ex), X(ez), 0.2 * U, 0, Math.PI * 2); g.fill();
    }
    // Wiesen
    for (const p of this.patches) {
      g.fillStyle = p.shade ? P.meadow : P.meadow2;
      g.beginPath();
      for (const [cx, cz, r] of p.circles) { g.moveTo(X(cx) + r * U, X(cz)); g.arc(X(cx), X(cz), r * U, 0, Math.PI * 2); }
      g.fill();
    }
    // Pfad mit Rand
    const stroke = (w, c) => {
      g.strokeStyle = c; g.lineWidth = w * U; g.beginPath();
      this.path.forEach(([x, z], i) => (i ? g.lineTo(X(x), X(z)) : g.moveTo(X(x), X(z)))); g.stroke();
    };
    stroke(1.9, P.pathEdge); stroke(1.45, P.path);
    // Steinchen
    g.fillStyle = P.pebble;
    for (const [x, z, r] of this.pebbles) { g.beginPath(); g.arc(X(x), X(z), r * U, 0, Math.PI * 2); g.fill(); }
    // Runder Platz, auf dem der Partner steht
    g.fillStyle = P.plazaEdge; g.beginPath(); g.arc(X(0), X(0), 1.08 * U, 0, Math.PI * 2); g.fill();
    g.fillStyle = P.plaza; g.beginPath(); g.arc(X(0), X(0), 0.98 * U, 0, Math.PI * 2); g.fill();
    g.strokeStyle = P.plazaEdge; g.lineWidth = 0.045 * U;
    for (let i = 0; i < 8; i++) {
      const a = (i / 8) * Math.PI * 2;
      g.beginPath(); g.moveTo(X(Math.cos(a) * 0.72), X(Math.sin(a) * 0.72)); g.lineTo(X(Math.cos(a) * 0.92), X(Math.sin(a) * 0.92)); g.stroke();
    }
    if (!this.floorTex) {
      this.floorTex = new THREE.CanvasTexture(this.canvas);
      this.floorTex.colorSpace = THREE.SRGBColorSpace;
      this.floorTex.anisotropy = 16;
    }
    this.floorTex.needsUpdate = true;
    return this.floorTex;
  }

  // Blumen auf den Wiesen in der Nähe
  _flowers() {
    const R = rng(777), spots = [];
    while (spots.length < 150) {
      const a = R() * Math.PI * 2, r = 2.2 + R() * 11, x = Math.cos(a) * r, z = Math.sin(a) * r;
      if (this._inMeadow(x, z, -0.15)) spots.push([x, z, Math.floor(R() * 3), 0.6 + R() * 0.7]);
    }
    this.flowerData = spots;
    const geo = new THREE.OctahedronGeometry(0.042, 0); geo.translate(0, 0.05, 0);
    this.mat.flower = new THREE.MeshToonMaterial({ color: "#ffffff" });
    this.flowers = this._instanced(geo, this.mat.flower, spots.length, (d, i) => {
      d.position.set(spots[i][0], 0, spots[i][1]); d.scale.set(spots[i][3], spots[i][3] * 0.7, spots[i][3]);
    });
  }

  // Leuchtende Datenfelder: einzelne Gitterzellen, die langsam auf- und abblenden
  _tiles() {
    const n = 54, geo = new THREE.PlaneGeometry(0.92, 0.92);
    geo.rotateX(-Math.PI / 2);
    this.tileData = [];
    const used = new Set();
    while (this.tileData.length < n) {
      const [x, z] = this._ring(1.2, 15), cx = Math.floor(x), cz = Math.floor(z), key = cx + "," + cz;
      if (used.has(key) || !this._bare(cx + 0.5, cz + 0.5)) continue;
      used.add(key);
      this.tileData.push({ x: cx + 0.5, z: cz + 0.5, phase: this.rand() * 6, speed: 0.4 + this.rand() * 0.8 });
    }
    // Farbe je Feld über die Instanz-Farbe (blendet zwischen Boden- und Feldfarbe)
    this.tiles = this._instanced(geo, this.mat.tile, n, (d, i) => { d.position.set(this.tileData[i].x, 0.002, this.tileData[i].z); });
    this.tileColor = new THREE.Color();
  }

  // Bäume: Stamm + runde, kantige Krone
  _trees() {
    const n = 46, spots = Array.from({ length: n }, () => this._ring(7, 26));
    const size = spots.map(() => 0.45 + this.rand() * 0.6);
    const trunk = new THREE.CylinderGeometry(0.08, 0.12, 1, 6); trunk.translate(0, 0.5, 0);
    const crown = new THREE.IcosahedronGeometry(0.6, 0);
    this._instanced(trunk, this.mat.trunk, n, (d, i) => { d.position.set(spots[i][0], 0, spots[i][1]); d.scale.set(size[i], size[i] * 0.9, size[i]); });
    this._instanced(crown, this.mat.leaf, n, (d, i) => {
      d.position.set(spots[i][0], size[i] * 1.25, spots[i][1]); d.scale.setScalar(size[i]); d.rotation.set(this.rand(), this.rand() * 3, 0);
    });
    // kleine Grasbüschel näher dran
    const tuft = new THREE.ConeGeometry(0.12, 0.35, 4); tuft.translate(0, 0.17, 0);
    this._instanced(tuft, this.mat.grass, 90, (d) => {
      const [x, z] = this._ring(2.6, 16); d.position.set(x, 0, z); d.scale.setScalar(0.35 + this.rand() * 0.5); d.rotation.y = this.rand() * 3;
    });
  }

  _rocks() {
    const geo = new THREE.DodecahedronGeometry(0.4, 0);
    this._instanced(geo, this.mat.rock, 22, (d) => {
      const [x, z] = this._ring(5, 24), s = 0.3 + this.rand() * 0.7;
      d.position.set(x, s * 0.15, z); d.scale.set(s * 1.3, s * 0.8, s); d.rotation.set(this.rand(), this.rand() * 3, this.rand());
    });
  }

  // Daten-Kristalle: schmale Doppelpyramiden, teils in Gruppen
  _crystals() {
    const geo = new THREE.OctahedronGeometry(0.3, 0);
    const clusters = Array.from({ length: 9 }, () => this._ring(6, 22));
    this._instanced(geo, this.mat.crystal, 27, (d, i) => {
      const c = clusters[i % 9], s = 0.4 + this.rand() * 0.7;
      d.position.set(c[0] + (this.rand() - 0.5) * 0.9, s * 0.45, c[1] + (this.rand() - 0.5) * 0.9);
      d.scale.set(s * 0.55, s * 1.6, s * 0.55); d.rotation.set((this.rand() - 0.5) * 0.5, this.rand() * 3, (this.rand() - 0.5) * 0.5);
    });
  }

  // Schwebende Inseln: Grasplatte oben, Fels-Spitze nach unten
  _islands() {
    this.isles = [];
    for (let i = 0; i < 4; i++) {
      const g = new THREE.Group(), s = 0.8 + this.rand() * 0.8;
      const top = new THREE.Mesh(new THREE.CylinderGeometry(1, 0.95, 0.25, 7), this.mat.grass);
      const under = new THREE.Mesh(new THREE.ConeGeometry(0.95, 1.6, 7), this.mat.isle);
      under.rotation.x = Math.PI; under.position.y = -0.92;
      const tree = new THREE.Mesh(new THREE.IcosahedronGeometry(0.35, 0), this.mat.leaf); tree.position.set(0.3, 0.5, 0.1);
      g.add(top, under, tree);
      const [x, z] = this._ring(17, 25);
      g.position.set(x, 2.6 + this.rand() * 1.8, z); g.scale.setScalar(s); g.rotation.y = this.rand() * 3;
      g.userData = { y: g.position.y, phase: this.rand() * 6 };
      this.group.add(g); this.isles.push(g);
    }
  }

  // Daten-Würfel, die langsam schweben und sich drehen
  _cubes() {
    const n = 18;
    this.cubeData = Array.from({ length: n }, () => {
      const [x, z] = this._ring(5, 18);
      return { x, z, y: 0.8 + this.rand() * 2.6, s: 0.1 + this.rand() * 0.22, phase: this.rand() * 6, spin: 0.3 + this.rand() * 0.8 };
    });
    this.cubes = this._instanced(new THREE.BoxGeometry(1, 1, 1), this.mat.cube, n, () => {});
    this.dummy = new THREE.Object3D();
  }

  // Wolken aus flachgedrückten Kugeln, ziehen langsam um die Welt
  _clouds() {
    this.cloudRing = new THREE.Group();
    const ball = new THREE.SphereGeometry(1, 12, 8);
    for (let i = 0; i < 9; i++) {
      const c = new THREE.Group(), parts = 3 + Math.floor(this.rand() * 3);
      for (let k = 0; k < parts; k++) {
        const m = new THREE.Mesh(ball, this.mat.cloud), s = 0.4 + this.rand() * 0.45;
        m.position.set((k - parts / 2) * 0.55 + this.rand() * 0.2, this.rand() * 0.2, this.rand() * 0.3);
        m.scale.set(s * 1.2, s * 0.75, s);
        c.add(m);
      }
      const a = (i / 9) * Math.PI * 2 + this.rand() * 0.4, r = 26 + this.rand() * 6;
      c.position.set(Math.cos(a) * r, 4.2 + this.rand() * 2.2, Math.sin(a) * r);
      c.lookAt(0, c.position.y, 0);
      c.scale.setScalar(0.7 + this.rand() * 0.5);
      this.cloudRing.add(c);
    }
    this.group.add(this.cloudRing);
  }

  // Datenregen: dünne Lichtstriche fallen in der Ferne herab
  _rain() {
    const n = 90;
    this.rainData = Array.from({ length: n }, () => {
      const [x, z] = this._ring(10, 28);
      return { x, z, y: this.rand() * 8, v: 3 + this.rand() * 4, l: 0.6 + this.rand() * 1.4 };
    });
    this.rain = this._instanced(new THREE.BoxGeometry(0.035, 1, 0.035), this.mat.rain, n, () => {});
  }

  // Kleine Datenpunkte steigen rund um den Partner auf
  _motes() {
    const n = 46, pos = new Float32Array(n * 3);
    this.moteData = Array.from({ length: n }, () => {
      const [x, z] = this._ring(0.8, 5);
      return { x, z, y: this.rand() * 3, v: 0.15 + this.rand() * 0.35, phase: this.rand() * 6 };
    });
    const geo = new THREE.BufferGeometry(); geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    this.motes = new THREE.Points(geo, this.mat.mote); this.motes.frustumCulled = false;
    this.group.add(this.motes);
  }

  _stars() {
    const n = 260, pos = new Float32Array(n * 3);
    for (let i = 0; i < n; i++) {
      const a = this.rand() * Math.PI * 2, h = 0.03 + this.rand() * 0.5, r = 60;
      pos.set([Math.cos(a) * r * Math.cos(h), Math.sin(h) * r, Math.sin(a) * r * Math.cos(h)], i * 3);
    }
    const geo = new THREE.BufferGeometry(); geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    this.stars = new THREE.Points(geo, this.mat.stars); this.stars.frustumCulled = false;
    this.group.add(this.stars);
  }

  setTime(time) {
    const P = PALETTE[time] || PALETTE.day;
    this.tileBase = new THREE.Color(P.floor); this.tileTop = new THREE.Color(P.tile);
    const c = new THREE.Color();
    this.flowerData.forEach((f, i) => this.flowers.setColorAt(i, c.set(P.flowers[f[2]])));
    this.flowers.instanceColor.needsUpdate = true;
    for (const key of ["far", "near", "leaf", "trunk", "rock", "crystal", "cube", "cloud", "rain", "grass", "isle", "mote"]) this.mat[key].color.set(P[key]);
    this.starLevel = P.stars;
    this.stars.visible = P.stars > 0;
    this.mat.rain.opacity = time === "night" ? 0.8 : 0.5;
  }

  update(dt) {
    const t = (this.t += dt), d = this.dummy;
    this.cloudRing.rotation.y = t * 0.006;
    for (const g of this.isles) g.position.y = g.userData.y + Math.sin(t * 0.5 + g.userData.phase) * 0.35;
    this.cubeData.forEach((c, i) => {
      d.position.set(c.x, c.y + Math.sin(t * 0.8 + c.phase) * 0.3, c.z);
      d.rotation.set(t * c.spin * 0.6, t * c.spin, 0); d.scale.setScalar(c.s); d.updateMatrix();
      this.cubes.setMatrixAt(i, d.matrix);
    });
    this.cubes.instanceMatrix.needsUpdate = true;
    this.tileData.forEach((c, i) => {
      const k = Math.max(0, Math.sin(t * c.speed + c.phase));
      this.tiles.setColorAt(i, this.tileColor.copy(this.tileBase).lerp(this.tileTop, k));
    });
    this.tiles.instanceColor.needsUpdate = true;
    this.rainData.forEach((r, i) => {
      r.y -= r.v * dt; if (r.y < -r.l) r.y = 6 + Math.random() * 3;
      d.position.set(r.x, r.y + r.l / 2, r.z); d.rotation.set(0, 0, 0); d.scale.set(1, r.l, 1); d.updateMatrix();
      this.rain.setMatrixAt(i, d.matrix);
    });
    this.rain.instanceMatrix.needsUpdate = true;
    const pos = this.motes.geometry.attributes.position;
    this.moteData.forEach((m, i) => {
      m.y += m.v * dt; if (m.y > 3.2) m.y = 0;
      pos.setXYZ(i, m.x + Math.sin(t + m.phase) * 0.15, m.y, m.z + Math.cos(t + m.phase) * 0.15);
    });
    pos.needsUpdate = true;
    this.mat.mote.opacity = 0.85;
    if (this.stars.visible) this.mat.stars.opacity = this.starLevel * (0.75 + Math.sin(t * 1.7) * 0.25);
  }
}
