/** @typedef {{ source: string, date: string, licence: string }} Source */
/** @typedef {{ id: string, category: string[], properties?: Record<string, { value?: unknown, sources: Source[] }>, sources: Source[] }} Node */
/** @typedef {{ subject: string, predicate: string, object: string, qualifiers?: Record<string, unknown>, sources: Source[] }} Edge */
/** @typedef {{ transitive: boolean, domain_range: { domain: string, range: string }[] }} RelationDef */

export function sortKeys(value) {
  if (value === null || typeof value !== "object") return value;
  if (Array.isArray(value)) return value.map(sortKeys);
  const out = {};
  for (const k of Object.keys(value).sort()) out[k] = sortKeys(value[k]);
  return out;
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
  return [edge.subject, edge.predicate, edge.object, q].join("\0");
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

function categoryClosure(categories) {
  /** @type {Map<string, Set<string>>} */
  const memo = new Map();
  function ancestors(cat) {
    if (memo.has(cat)) return memo.get(cat);
    const parents = categories[cat];
    const set = new Set([cat]);
    if (Array.isArray(parents)) {
      for (const p of parents) {
        for (const a of ancestors(p)) set.add(a);
      }
    }
    memo.set(cat, set);
    return set;
  }
  return ancestors;
}

function subsumes(ancestors, nodeCats, target) {
  for (const c of nodeCats) {
    if (!ancestors(c).has(target)) continue;
    return true;
  }
  return false;
}

function checkCanonicalLines(text, records, kind) {
  const issues = [];
  const lines = text.replace(/\n$/, "") === "" ? [] : text.replace(/\n$/, "").split("\n");
  if (lines.length !== records.length) {
    issues.push(`${kind}: line count does not match parsed records`);
  }
  for (let i = 0; i < records.length; i++) {
    const canonical = JSON.stringify(sortKeys(records[i]));
    if (lines[i] !== canonical) issues.push(`${kind}: line ${i + 1} is not canonical (sorted keys)`);
  }
  for (let i = 1; i < records.length; i++) {
    const prev = kind === "nodes.jsonl" ? records[i - 1].id : edgeSortKey(records[i - 1]);
    const cur = kind === "nodes.jsonl" ? records[i].id : edgeSortKey(records[i]);
    if (cur <= prev) issues.push(`${kind}: lines not sorted at index ${i}`);
  }
  return issues;
}

/**
 * @param {{ nodesText: string, edgesText: string, relations: Record<string, RelationDef>, categories: Record<string, string[]> }} input
 * @returns {string[]}
 */
export function validateGraph(input) {
  const { nodesText, edgesText, relations, categories } = input;
  const issues = [];
  const nodes = parseJsonl(nodesText);
  const edges = parseJsonl(edgesText);
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const ancestors = categoryClosure(categories);

  issues.push(...checkCanonicalLines(nodesText, nodes, "nodes.jsonl"));
  issues.push(...checkCanonicalLines(edgesText, edges, "edges.jsonl"));

  for (let i = 0; i < nodes.length; i++) {
    const n = nodes[i];
    const p = `nodes[${i}]`;
    if (typeof n.id !== "string" || n.id === "") issues.push(`${p}.id: required non-empty string`);
    if (!Array.isArray(n.category) || n.category.length === 0) {
      issues.push(`${p}.category: required non-empty array`);
    }
    issues.push(...checkSources(n.sources, p));
    if (n.properties != null) {
      if (typeof n.properties !== "object" || Array.isArray(n.properties)) {
        issues.push(`${p}.properties: must be an object when present`);
      } else {
        for (const [key, prop] of Object.entries(n.properties)) {
          if (prop && typeof prop === "object" && "sources" in prop) {
            issues.push(...checkSources(prop.sources, `${p}.properties.${key}`));
          }
        }
      }
    }
  }

  for (let i = 0; i < edges.length; i++) {
    const e = edges[i];
    const p = `edges[${i}]`;
    for (const field of ["subject", "predicate", "object"]) {
      if (typeof e[field] !== "string" || e[field] === "") {
        issues.push(`${p}.${field}: required non-empty string`);
      }
    }
    if (e.qualifiers != null && (typeof e.qualifiers !== "object" || Array.isArray(e.qualifiers))) {
      issues.push(`${p}.qualifiers: must be an object when present`);
    }
    issues.push(...checkSources(e.sources, p));
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
  for (const n of a.nodes) nodeMap.set(n.id, n);
  for (const n of b.nodes) nodeMap.set(n.id, n);
  const edgeMap = new Map();
  for (const e of a.edges) edgeMap.set(edgeSortKey(e), e);
  for (const e of b.edges) edgeMap.set(edgeSortKey(e), e);
  const nodes = [...nodeMap.values()].sort((x, y) => x.id.localeCompare(y.id));
  const edges = [...edgeMap.values()].sort((x, y) => edgeSortKey(x).localeCompare(edgeSortKey(y)));
  return { nodes, edges };
}

/** @param {{ nodes: Node[], edges: Edge[] }} graph */
export function serializeGraph(graph) {
  const nodesText = graph.nodes.map((n) => JSON.stringify(sortKeys(n))).join("\n");
  const edgesText = graph.edges.map((e) => JSON.stringify(sortKeys(e))).join("\n");
  return { nodesText, edgesText };
}
