#!/usr/bin/env node
// Queen's Domain – extraction des acteurs et de leurs positions depuis les exports JSON de FModel.
// Version 2 (acteurs attachés à un parent correctement résolus).
// Usage : node extract-map-data.js <dossier contenant les .json des niveaux> [fichier de sortie]
// Lit chaque .json (un par niveau), ne modifie rien, écrit un seul fichier compact.
const fs = require('fs');
const path = require('path');

const inDir = process.argv[2];
const outFile = process.argv[3] || 'queens-domain-actors.json';
if (!inDir) { console.error('Usage : node extract-map-data.js <dossier> [sortie.json]'); process.exit(1); }

const shortName = (ref) => (ref && ref.ObjectName ? ref.ObjectName.split('.').pop().replace(/'$/, '') : null);
const r1 = (n) => Math.round(n * 10) / 10;

function simplify(v, depth = 0) {
  if (v === null || typeof v === 'number' || typeof v === 'boolean') return v;
  if (typeof v === 'string') return v.length > 200 ? v.slice(0, 200) : v;
  if (Array.isArray(v)) {
    if (depth > 1 || v.length > 40) return undefined;
    const a = v.map((x) => simplify(x, depth + 1)).filter((x) => x !== undefined);
    return a.length ? a : undefined;
  }
  if (typeof v === 'object') {
    if ('ObjectName' in v && 'ObjectPath' in v) {
      const cls = v.ObjectName.split("'")[0];
      return cls + ':' + (shortName(v) || '');
    }
    if ('AssetPathName' in v) return v.AssetPathName || undefined;
    if (depth > 1) return undefined;
    const o = {};
    for (const [k, x] of Object.entries(v)) { const s = simplify(x, depth + 1); if (s !== undefined) o[k] = s; }
    return Object.keys(o).length ? o : undefined;
  }
  return undefined;
}

const SKIP_PROPS = new Set(['RootComponent', 'BlueprintCreatedComponents', 'UberGraphFrame', 'GUIDs', 'SaveHelper',
  'UpdateDissolve', 'DissolveStarted', 'OnLoadedAsDissolved', 'DissolveFinished', 'DefaultSceneRoot']);

function processLevel(file) {
  const level = path.basename(file, '.json');
  let data;
  try { data = JSON.parse(fs.readFileSync(file, 'utf8').replace(/^﻿/, '')); }
  catch (e) { console.error(`  ! ${level} : JSON illisible (${e.message})`); return null; }
  if (!Array.isArray(data)) { console.error(`  ! ${level} : format inattendu`); return null; }

  const comps = new Map(); // "acteur/composant" -> objet
  for (const o of data) {
    const outer = o.Outer && o.Outer.ObjectName ? shortName(o.Outer) : null;
    if (outer) comps.set(outer + '/' + o.Name, o);
  }
  const actors = [];
  let noPos = 0;
  for (const o of data) {
    const outerName = o.Outer && o.Outer.ObjectName ? o.Outer.ObjectName : '';
    if (!outerName.startsWith("Level'")) continue; // acteurs placés directement dans le niveau
    const p = o.Properties || {};
    const a = { t: o.Type, n: o.Name };
    const root = p.RootComponent ? comps.get(o.Name + '/' + shortName(p.RootComponent)) : null;
    const rp = root && root.Properties ? root.Properties : null;
    if (rp && rp.RelativeLocation) {
      a.x = r1(rp.RelativeLocation.X); a.y = r1(rp.RelativeLocation.Y); a.z = r1(rp.RelativeLocation.Z);
    } else if (root) { a.x = 0; a.y = 0; a.z = 0; } else { noPos++; }
    if (rp && rp.RelativeRotation) a.yaw = r1(rp.RelativeRotation.Yaw || 0);
    if (rp && rp.AttachParent && rp.AttachParent.ObjectName) {
      // position relative à un autre acteur : on note l'acteur parent (et non son composant)
      const m = /PersistentLevel\.([^.']+)/.exec(rp.AttachParent.ObjectName);
      a.attach = m ? m[1] : shortName(rp.AttachParent);
    }
    if (Array.isArray(p.GUIDs) && p.GUIDs.length) a.g = p.GUIDs;
    const extra = {};
    for (const [k, v] of Object.entries(p)) {
      if (SKIP_PROPS.has(k)) continue;
      const s = simplify(v);
      if (s !== undefined) extra[k] = s;
    }
    if (Object.keys(extra).length) a.p = extra;
    actors.push(a);
  }
  console.log(`  ${level} : ${data.length} objets, ${actors.length} acteurs (${noPos} sans position)`);
  return { level, actors };
}

function listJson(dir) {
  let out = [];
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const f = path.join(dir, e.name);
    if (e.isDirectory()) out = out.concat(listJson(f));
    else if (e.name.toLowerCase().endsWith('.json')) out.push(f);
  }
  return out;
}

const files = listJson(inDir).filter((f) => path.resolve(f) !== path.resolve(outFile)).sort();
if (!files.length) { console.error('Aucun fichier .json trouvé dans ' + inDir); process.exit(1); }
console.log(`${files.length} fichier(s) trouvé(s)`);
const levels = [];
for (const f of files) { const r = processLevel(f); if (r && r.actors.length) levels.push(r); }
fs.writeFileSync(outFile, JSON.stringify({ game: "Queen's Domain", generated: new Date().toISOString(), levels }));
const total = levels.reduce((s, l) => s + l.actors.length, 0);
console.log(`\nTerminé : ${levels.length} niveau(x), ${total} acteurs -> ${outFile} (${(fs.statSync(outFile).size / 1048576).toFixed(1)} Mo)`);
