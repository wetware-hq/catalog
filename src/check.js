import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

/** @typedef {{ ref: string, level: "human"|"animal"|"in_vitro"|"claim" }} Citation */
/** @typedef {{ binders: Record<string, { status: string }>, targets: Record<string, Record<string, never>>, edges: Record<string, Record<string, Citation[]>> }} Graph */

const BINDER_STATUSES = ["approved", "investigational", "unapproved"];
const LEVELS = ["animal", "claim", "human", "in_vitro"];
const CHEMBL_ID = /^CHEMBL\d+$/;
const BINDER_SEQ = /^seq:[A-Z*]+$/;
const UNIPROT_ID = /^[A-NR-Z][0-9]([A-Z][A-Z0-9]{2}[0-9]){1,2}$/;
const PUBMED_REF = /^\d+$/;
const DOI_REF = /^10\.\S+$/;

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

function isBinderId(id) {
  return CHEMBL_ID.test(id) || BINDER_SEQ.test(id);
}

function isTargetId(id) {
  return UNIPROT_ID.test(id);
}

function isRef(ref) {
  return PUBMED_REF.test(ref) || DOI_REF.test(ref);
}

function citationKey(c) {
  return `${c.ref}\0${c.level}`;
}

export function canonicalizeCitation(c) {
  return sortKeys(c);
}

export function canonicalizeCitations(list) {
  const byKey = new Map();
  for (const raw of list ?? []) byKey.set(citationKey(raw), canonicalizeCitation(raw));
  return [...byKey.values()].sort((a, b) => cmp(citationKey(a), citationKey(b)));
}

function mergeStatus(a, b) {
  return cmp(a, b) <= 0 ? a : b;
}

/** @param {Graph} graph */
export function canonicalizeGraph(graph) {
  const binders = {};
  for (const id of Object.keys(graph.binders ?? {}).sort()) {
    binders[id] = sortKeys({ status: graph.binders[id].status });
  }
  const targets = {};
  for (const id of Object.keys(graph.targets ?? {}).sort()) {
    targets[id] = {};
  }
  const edges = {};
  for (const binder of Object.keys(graph.edges ?? {}).sort()) {
    const row = {};
    for (const target of Object.keys(graph.edges[binder] ?? {}).sort()) {
      row[target] = canonicalizeCitations(graph.edges[binder][target]);
    }
    edges[binder] = row;
  }
  return sortKeys({ binders, targets, edges });
}

export function canonicalText(graph) {
  return JSON.stringify(canonicalizeGraph(graph));
}

function checkCitationArray(list, path, issues) {
  if (!Array.isArray(list) || list.length === 0) {
    issues.push(`${path}: at least one citation required`);
    return;
  }
  for (let i = 0; i < list.length; i++) {
    const c = list[i];
    const p = `${path}[${i}]`;
    if (typeof c?.ref !== "string" || !isRef(c.ref)) issues.push(`${p}.ref: PubMed id or DOI required`);
    if (!LEVELS.includes(c?.level)) issues.push(`${p}.level: must be human|animal|in_vitro|claim`);
  }
  const canon = canonicalizeCitations(list);
  if (JSON.stringify(canon) !== JSON.stringify(sortKeys(list))) {
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
  for (const key of ["binders", "targets", "edges"]) {
    if (graph[key] == null || typeof graph[key] !== "object" || Array.isArray(graph[key])) {
      issues.push(`graph.${key}: must be an object`);
    }
  }
  if (issues.length) return issues;

  for (const [id, body] of Object.entries(graph.binders)) {
    const p = `binders.${id}`;
    if (!isBinderId(id)) issues.push(`${p}: invalid binder id (CHEMBL… or seq:SEQUENCE)`);
    if (!BINDER_STATUSES.includes(body?.status)) issues.push(`${p}.status: must be approved|investigational|unapproved`);
    if (body && typeof body === "object" && Object.keys(body).length !== 1) {
      issues.push(`${p}: only status field allowed`);
    }
  }

  for (const [id, body] of Object.entries(graph.targets)) {
    const p = `targets.${id}`;
    if (!isTargetId(id)) issues.push(`${p}: invalid UniProt accession`);
    if (body && typeof body === "object" && Object.keys(body).length !== 0) {
      issues.push(`${p}: must be {}`);
    }
  }

  for (const [binder, row] of Object.entries(graph.edges)) {
    const bp = `edges.${binder}`;
    if (!isBinderId(binder)) issues.push(`${bp}: invalid binder id`);
    if (!(binder in graph.binders)) issues.push(`${bp}: binder missing from binders`);
    if (row == null || typeof row !== "object" || Array.isArray(row)) {
      issues.push(`${bp}: must be an object`);
      continue;
    }
    for (const [target, citations] of Object.entries(row)) {
      const tp = `${bp}.${target}`;
      if (!isTargetId(target)) issues.push(`${tp}: invalid target id`);
      if (!(target in graph.targets)) issues.push(`${tp}: target missing from targets`);
      checkCitationArray(citations, tp, issues);
    }
  }

  return issues;
}

/** @param {Graph} a @param {Graph} b */
export function mergeGraphs(a, b) {
  const binders = { ...a.binders };
  for (const [id, body] of Object.entries(b.binders ?? {})) {
    binders[id] = id in binders ? { status: mergeStatus(binders[id].status, body.status) } : { ...body };
  }
  const targets = { ...a.targets, ...b.targets };
  const edges = structuredClone(a.edges);
  for (const [binder, row] of Object.entries(b.edges ?? {})) {
    if (!edges[binder]) edges[binder] = {};
    for (const [target, citations] of Object.entries(row)) {
      edges[binder][target] = edges[binder][target]
        ? canonicalizeCitations([...edges[binder][target], ...citations])
        : canonicalizeCitations(citations);
    }
  }
  return canonicalizeGraph({ binders, targets, edges });
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
  const canon = canonicalText(graph);
  if (text.replace(/\n$/, "") !== canon) issues.push(`${path}: file is not canonical`);
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
