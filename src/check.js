import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

/** @typedef {{ source: string, date: string, licence: string }} Source */
/** @typedef {{ id: string, category: string[], properties?: Record<string, { value?: unknown, sources: Source[] }>, sources: Source[] }} Node */
/** @typedef {{ subject: string, predicate: string, object: string, qualifiers?: Record<string, unknown>, sources: Source[] }} Edge */

export function cmp(a, b) {
  if (a < b) return -1;
  if (a > b) return 1;
  return 0;
}

export function sortKeys(value) {
  if (value === null || typeof value !== "object") return value;
  if (Array.isArray(value)) return value.map(sortKeys);
  const out = {};
  for (const k of Object.keys(value).sort()) out[k] = sortKeys(value[k]);
  return out;
}

function sourceKey(s) {
  return `${s.source}\0${s.date}\0${s.licence}`;
}

export function canonicalizeSources(sources) {
  const byKey = new Map();
  for (const raw of sources ?? []) {
    const s = sortKeys(raw);
    byKey.set(sourceKey(s), s);
  }
  return [...byKey.values()].sort((a, b) => cmp(sourceKey(a), sourceKey(b)));
}

export function canonicalizeCategories(cats) {
  return [...new Set(cats ?? [])].sort(cmp);
}

export function canonicalizeNode(node) {
  const properties = {};
  for (const [key, prop] of Object.entries(node.properties ?? {})) {
    if (prop && typeof prop === "object") {
      properties[key] = sortKeys({ ...prop, sources: canonicalizeSources(prop.sources) });
    }
  }
  return sortKeys({
    id: node.id,
    category: canonicalizeCategories(node.category),
    properties,
    sources: canonicalizeSources(node.sources),
  });
}

export function canonicalizeEdge(edge) {
  return sortKeys({
    subject: edge.subject,
    predicate: edge.predicate,
    object: edge.object,
    qualifiers: sortKeys(edge.qualifiers ?? {}),
    sources: canonicalizeSources(edge.sources),
  });
}

export function canonicalLine(record, kind) {
  const body = kind === "node" ? canonicalizeNode(record) : canonicalizeEdge(record);
  return JSON.stringify(body);
}

export function parseJsonl(text) {
  const trimmed = text.replace(/\n$/, "");
  if (trimmed === "") return [];
  return trimmed.split("\n").map((line, i) => {
    try {
      return JSON.parse(line);
    } catch (e) {
      throw new Error(`jsonl line ${i + 1}: ${e.message}`);
    }
  });
}

export function edgeSortKey(edge) {
  const q = JSON.stringify(sortKeys(edge.qualifiers ?? {}));
  return `${edge.subject}\0${edge.predicate}\0${edge.object}\0${q}`;
}

export function checkSources(sources, path) {
  const issues = [];
  if (!Array.isArray(sources) || sources.length === 0) {
    issues.push(`${path}: at least one source required`);
    return issues;
  }
  for (let i = 0; i < sources.length; i++) {
    const s = sources[i];
    for (const field of ["source", "date", "licence"]) {
      if (typeof s?.[field] !== "string" || s[field] === "") {
        issues.push(`${path}.sources[${i}].${field}: required non-empty string`);
      }
    }
  }
  return issues;
}

export function validateCategoryVocabulary(categories) {
  const issues = [];
  for (const [cat, parents] of Object.entries(categories)) {
    if (!Array.isArray(parents)) issues.push(`categories.json: "${cat}" must map to a parent array`);
    else for (const p of parents) {
      if (!(p in categories)) issues.push(`categories.json: "${cat}" references unknown parent "${p}"`);
    }
  }
  const visiting = new Set();
  const done = new Set();
  function dfs(cat) {
    if (done.has(cat)) return false;
    if (visiting.has(cat)) return true;
    visiting.add(cat);
    for (const p of categories[cat] ?? []) {
      if (dfs(p)) return true;
    }
    visiting.delete(cat);
    done.add(cat);
    return false;
  }
  for (const cat of Object.keys(categories)) {
    if (dfs(cat)) {
      issues.push("categories.json: cycle in category hierarchy");
      break;
    }
  }
  return issues;
}

function categoryClosure(categories) {
  const memo = new Map();
  function ancestors(cat) {
    if (memo.has(cat)) return memo.get(cat);
    const set = new Set([cat]);
    for (const p of categories[cat] ?? []) {
      for (const a of ancestors(p)) set.add(a);
    }
    memo.set(cat, set);
    return set;
  }
  return ancestors;
}

function subsumes(ancestors, nodeCats, target) {
  for (const c of nodeCats) {
    if (ancestors(c).has(target)) return true;
  }
  return false;
}

function checkCanonicalLines(text, records, kind) {
  const issues = [];
  const file = kind === "node" ? "nodes.jsonl" : "edges.jsonl";
  const lines = text.replace(/\n$/, "") === "" ? [] : text.replace(/\n$/, "").split("\n");
  if (lines.length !== records.length) issues.push(`${file}: line count does not match parsed records`);
  for (let i = 0; i < records.length; i++) {
    const canonical = canonicalLine(records[i], kind);
    if (lines[i] !== canonical) issues.push(`${file}: line ${i + 1} is not canonical`);
  }
  for (let i = 1; i < records.length; i++) {
    const prev = kind === "node" ? records[i - 1].id : edgeSortKey(records[i - 1]);
    const cur = kind === "node" ? records[i].id : edgeSortKey(records[i]);
    if (cmp(cur, prev) <= 0) issues.push(`${file}: lines not sorted at index ${i}`);
  }
  return issues;
}

function mergeNodes(a, b) {
  const properties = { ...(a.properties ?? {}) };
  for (const [key, prop] of Object.entries(b.properties ?? {})) {
    const left = properties[key];
    properties[key] = left
      ? { ...left, ...prop, sources: [...(left.sources ?? []), ...(prop?.sources ?? [])] }
      : prop;
  }
  return canonicalizeNode({
    id: a.id,
    category: [...(a.category ?? []), ...(b.category ?? [])],
    properties,
    sources: [...(a.sources ?? []), ...(b.sources ?? [])],
  });
}

function mergeEdges(a, b) {
  return canonicalizeEdge({ ...a, sources: [...(a.sources ?? []), ...(b.sources ?? [])] });
}

/**
 * @param {{ nodesText: string, edgesText: string, relations: Record<string, unknown>, categories: Record<string, string[]> }} input
 * @returns {string[]}
 */
export function validateGraph(input) {
  const { nodesText, edgesText, relations, categories } = input;
  const issues = validateCategoryVocabulary(categories);
  const nodes = parseJsonl(nodesText);
  const edges = parseJsonl(edgesText);
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const ancestors = issues.length ? () => new Set() : categoryClosure(categories);

  issues.push(...checkCanonicalLines(nodesText, nodes, "node"));
  issues.push(...checkCanonicalLines(edgesText, edges, "edge"));

  for (let i = 0; i < nodes.length; i++) {
    const n = nodes[i];
    const p = `nodes[${i}]`;
    if (typeof n.id !== "string" || n.id === "") issues.push(`${p}.id: required non-empty string`);
    if (!Array.isArray(n.category) || n.category.length === 0) issues.push(`${p}.category: required non-empty array`);
    else {
      for (const c of n.category) {
        if (!(c in categories)) issues.push(`${p}.category: unknown category "${c}"`);
      }
      const canonCats = canonicalizeCategories(n.category);
      if (canonCats.length !== n.category.length || canonCats.some((c, j) => c !== n.category[j])) {
        issues.push(`${p}.category: must be sorted unique strings`);
      }
    }
    issues.push(...checkSources(n.sources, p));
    const canonSrc = canonicalizeSources(n.sources);
    if (JSON.stringify(canonSrc) !== JSON.stringify(sortKeys(n.sources))) {
      issues.push(`${p}.sources: must be sorted and deduplicated`);
    }
    if (n.properties != null) {
      if (typeof n.properties !== "object" || Array.isArray(n.properties)) {
        issues.push(`${p}.properties: must be an object when present`);
      } else {
        for (const [key, prop] of Object.entries(n.properties)) {
          if (prop && typeof prop === "object" && "sources" in prop) {
            issues.push(...checkSources(prop.sources, `${p}.properties.${key}`));
            const cs = canonicalizeSources(prop.sources);
            if (JSON.stringify(cs) !== JSON.stringify(sortKeys(prop.sources))) {
              issues.push(`${p}.properties.${key}.sources: must be sorted and deduplicated`);
            }
          }
        }
      }
    }
  }

  for (let i = 0; i < edges.length; i++) {
    const e = edges[i];
    const p = `edges[${i}]`;
    for (const field of ["subject", "predicate", "object"]) {
      if (typeof e[field] !== "string" || e[field] === "") issues.push(`${p}.${field}: required non-empty string`);
    }
    if (e.qualifiers != null && (typeof e.qualifiers !== "object" || Array.isArray(e.qualifiers))) {
      issues.push(`${p}.qualifiers: must be an object when present`);
    }
    issues.push(...checkSources(e.sources, p));
    const canonSrc = canonicalizeSources(e.sources);
    if (JSON.stringify(canonSrc) !== JSON.stringify(sortKeys(e.sources))) {
      issues.push(`${p}.sources: must be sorted and deduplicated`);
    }
    if (!byId.has(e.subject)) issues.push(`${p}: subject node "${e.subject}" missing`);
    if (!byId.has(e.object)) issues.push(`${p}: object node "${e.object}" missing`);
    const def = relations[e.predicate];
    if (!def) {
      issues.push(`${p}: unknown predicate "${e.predicate}"`);
      continue;
    }
    const subj = byId.get(e.subject);
    const obj = byId.get(e.object);
    if (subj && obj && Array.isArray(def.domain_range)) {
      const ok = def.domain_range.some(
        ({ domain, range }) => subsumes(ancestors, subj.category, domain) && subsumes(ancestors, obj.category, range),
      );
      if (!ok) issues.push(`${p}: node categories violate domain/range for "${e.predicate}"`);
    }
  }

  return issues;
}

/** @param {{ nodes: Node[], edges: Edge[] }} a @param {{ nodes: Node[], edges: Edge[] }} b */
export function mergeGraphs(a, b) {
  const nodeMap = new Map();
  for (const n of a.nodes) nodeMap.set(n.id, canonicalizeNode(n));
  for (const n of b.nodes) {
    const prev = nodeMap.get(n.id);
    nodeMap.set(n.id, prev ? mergeNodes(prev, n) : canonicalizeNode(n));
  }
  const edgeMap = new Map();
  for (const e of a.edges) edgeMap.set(edgeSortKey(e), canonicalizeEdge(e));
  for (const e of b.edges) {
    const k = edgeSortKey(e);
    const prev = edgeMap.get(k);
    edgeMap.set(k, prev ? mergeEdges(prev, e) : canonicalizeEdge(e));
  }
  const nodes = [...nodeMap.values()].sort((x, y) => cmp(x.id, y.id));
  const edges = [...edgeMap.values()].sort((x, y) => cmp(edgeSortKey(x), edgeSortKey(y)));
  return { nodes, edges };
}

/** @param {{ nodes: Node[], edges: Edge[] }} graph */
export function serializeGraph(graph) {
  const nodesText = graph.nodes.map((n) => canonicalLine(n, "node")).join("\n");
  const edgesText = graph.edges.map((e) => canonicalLine(e, "edge")).join("\n");
  return { nodesText, edgesText };
}

export function validateGraphDir(dir) {
  const relations = JSON.parse(readFileSync(join(dir, "relations.json"), "utf8"));
  const categories = JSON.parse(readFileSync(join(dir, "categories.json"), "utf8"));
  const nodesText = readFileSync(join(dir, "nodes.jsonl"), "utf8");
  const edgesText = readFileSync(join(dir, "edges.jsonl"), "utf8");
  return validateGraph({ nodesText, edgesText, relations, categories });
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  const dir = process.argv[2];
  if (!dir) {
    console.error("usage: node src/check.js <graph-dir>");
    process.exit(2);
  }
  const issues = validateGraphDir(dir);
  if (issues.length) {
    for (const line of issues) console.error(line);
    process.exit(1);
  }
}
