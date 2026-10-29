import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

export const STATUS_ORDER = ["approved", "investigational", "unapproved"];
export const GRADE_ORDER = [
  "meta",
  "rct",
  "trial",
  "observational",
  "case",
  "animal",
  "in_vitro",
  "claim",
];

const BINDER_KEY = /^(chembl:CHEMBL\d+|seq:[A-Z*]+)$/;
const TARGET_KEY = /^uniprot:[A-Z][A-Z0-9]{5,9}$/;
const CITATION_KEY = /^(pmid:\d+|doi:.+)$/;

/** @typedef {{ pair: Record<string, Record<string, string[]>>, status: Record<string, string>, ref: Record<string, string> }} Graph */

export function cmp(a, b) {
  if (a < b) return -1;
  if (a > b) return 1;
  return 0;
}

export function sortKeys(value) {
  if (typeof value === "number") return value;
  if (value === null || typeof value !== "object") return value;
  if (Array.isArray(value)) return value.map(sortKeys);
  const out = {};
  for (const k of Object.keys(value).sort()) out[k] = sortKeys(value[k]);
  return out;
}

function validateNumbers(value, path, issues) {
  if (typeof value === "number") {
    if (!Number.isSafeInteger(value)) issues.push(`${path}: numbers must be safe integers (use strings for decimals)`);
    return;
  }
  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i++) validateNumbers(value[i], `${path}[${i}]`, issues);
  } else if (value !== null && typeof value === "object") {
    for (const [k, v] of Object.entries(value)) validateNumbers(v, `${path}.${k}`, issues);
  }
}

function isBinderKey(key) {
  return BINDER_KEY.test(key);
}

function isTargetKey(key) {
  return TARGET_KEY.test(key);
}

function isCitationKey(key) {
  return CITATION_KEY.test(key);
}

export function canonicalizeCitationList(list) {
  return [...new Set(list ?? [])].sort(cmp);
}

function weaker(order, a, b) {
  return order[Math.max(order.indexOf(a), order.indexOf(b))];
}

/** @param {Graph} graph */
export function canonicalizeGraph(graph) {
  const pair = {};
  for (const binder of Object.keys(graph.pair ?? {}).sort()) {
    const row = {};
    for (const target of Object.keys(graph.pair[binder] ?? {}).sort()) {
      row[target] = canonicalizeCitationList(graph.pair[binder][target]);
    }
    pair[binder] = row;
  }
  const status = {};
  for (const k of Object.keys(graph.status ?? {}).sort()) status[k] = graph.status[k];
  const ref = {};
  for (const k of Object.keys(graph.ref ?? {}).sort()) ref[k] = graph.ref[k];
  return sortKeys({ pair, ref, status });
}

export function canonicalText(graph) {
  return JSON.stringify(canonicalizeGraph(graph));
}

function checkCitationList(list, path, issues) {
  if (!Array.isArray(list) || list.length === 0) {
    issues.push(`${path}: at least one citation required`);
    return;
  }
  for (let i = 0; i < list.length; i++) {
    if (typeof list[i] !== "string" || !isCitationKey(list[i])) {
      issues.push(`${path}[${i}]: must be pmid:… or doi:…`);
    }
  }
  const canon = canonicalizeCitationList(list);
  if (canon.length !== list.length || canon.some((c, i) => c !== list[i])) {
    issues.push(`${path}: citations must be sorted and deduplicated`);
  }
}

/** @param {Graph} graph @returns {string[]} */
export function validateGraph(graph) {
  const issues = [];
  validateNumbers(graph, "graph", issues);
  if (!graph || typeof graph !== "object" || Array.isArray(graph)) {
    issues.push("graph: must be an object");
    return issues;
  }
  for (const key of ["pair", "status", "ref"]) {
    if (graph[key] == null || typeof graph[key] !== "object" || Array.isArray(graph[key])) {
      issues.push(`graph.${key}: must be an object`);
    }
  }
  if (issues.length) return issues;

  for (const [binder, status] of Object.entries(graph.status)) {
    const p = `status.${binder}`;
    if (!isBinderKey(binder)) {
      if (isTargetKey(binder)) issues.push(`${p}: target key cannot be a binder`);
      else issues.push(`${p}: invalid binder key`);
    }
    if (!STATUS_ORDER.includes(status)) issues.push(`${p}: invalid status`);
  }

  for (const [cite, grade] of Object.entries(graph.ref)) {
    const p = `ref.${cite}`;
    if (!isCitationKey(cite)) issues.push(`${p}: invalid citation key`);
    if (!GRADE_ORDER.includes(grade)) issues.push(`${p}: invalid grade`);
  }

  for (const [binder, row] of Object.entries(graph.pair)) {
    const bp = `pair.${binder}`;
    if (!isBinderKey(binder)) {
      if (isTargetKey(binder)) issues.push(`${bp}: target key cannot be a binder (outer pair key)`);
      else issues.push(`${bp}: invalid binder key`);
    }
    if (!(binder in graph.status)) issues.push(`${bp}: binder missing from status`);
    if (row == null || typeof row !== "object" || Array.isArray(row)) {
      issues.push(`${bp}: must be an object`);
      continue;
    }
    for (const [target, citations] of Object.entries(row)) {
      const tp = `${bp}.${target}`;
      if (!isTargetKey(target)) {
        if (isBinderKey(target)) issues.push(`${tp}: binder key cannot be a target (inner pair key)`);
        else issues.push(`${tp}: invalid target key`);
      }
      checkCitationList(citations, tp, issues);
      for (const c of citations ?? []) {
        if (!(c in graph.ref)) issues.push(`${tp}: citation "${c}" missing from ref`);
      }
    }
  }

  return issues;
}

function mergePair(a, b) {
  const pair = structuredClone(a);
  for (const [binder, row] of Object.entries(b)) {
    if (!pair[binder]) pair[binder] = {};
    for (const [target, citations] of Object.entries(row)) {
      pair[binder][target] = pair[binder][target]
        ? canonicalizeCitationList([...pair[binder][target], ...citations])
        : canonicalizeCitationList(citations);
    }
  }
  return pair;
}

function mergeScalars(a, b, order) {
  const out = { ...a };
  for (const [k, v] of Object.entries(b)) {
    out[k] = k in out ? weaker(order, out[k], v) : v;
  }
  return out;
}

/** @param {Graph} a @param {Graph} b */
export function mergeGraphs(a, b) {
  return canonicalizeGraph({
    pair: mergePair(a.pair ?? {}, b.pair ?? {}),
    status: mergeScalars(a.status ?? {}, b.status ?? {}, STATUS_ORDER),
    ref: mergeScalars(a.ref ?? {}, b.ref ?? {}, GRADE_ORDER),
  });
}

export function validateGraphFile(path) {
  const text = readFileSync(path, "utf8");
  let graph;
  try {
    graph = JSON.parse(text);
  } catch (e) {
    return [`${path}: invalid JSON (${e.message})`];
  }
  const issues = validateGraph(graph);
  if (text.replace(/\n$/, "") !== canonicalText(graph)) issues.push(`${path}: file is not canonical`);
  return issues;
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const file = process.argv[2];
  if (!file) {
    console.error("usage: node src/check.js <graph.json>");
    process.exit(2);
  }
  const issues = validateGraphFile(file);
  if (issues.length) {
    for (const line of issues) console.error(line);
    process.exit(1);
  }
}
