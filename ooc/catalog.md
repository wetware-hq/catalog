::meta
title: Catalog traversal index
version: 1
updated: 2026-11-09
domain: catalog|orchestration
scope: all
catalogue-version: 2
governs: docs/follow-agent-contract.md
checksum: sha256:4f3112ad7fe2adc976742599824047fea77978fe873a2458800ea3525d03f4ff
::end

::schema
node-types: [route, assertion, meta]
edge-types: [requires, precedes, see-also]
scope-levels: [all, orchestrator, worker, readonly]
::end

::index
# id | type | scope | conf | keywords
banner | meta | all | 1.00 | academic, research, oversight, banner
protocol | meta | all | 1.00 | search-index, resolve-context, route, endpoint, precedes
law | meta | all | 1.00 | contract, governs, specbase, markdown, oracle
read | route | all | 0.99 | read, rank, rows, pair, preclinical, catalogue
resolve | route | all | 0.99 | resolve, key, aa, helm, uniprot, identity
propose | route | all | 0.97 | propose, intake, proposals, pmid, triple
falsify | route | all | 0.99 | falsify, attack, predicate, survivor, swarm
router | route | all | 0.99 | navigate, route, initialization, minimum-read
traces | route | all | 0.95 | trace, act, merkle, halt, seal, og-root
design | route | all | 0.95 | design, campaign, epitope, calibrate, bench, sink
w004 | route | all | 0.90 | christmas, eveleigh, ratio, talent
oracle-open | assertion | all | 1.00 | predicate-16, not-discharged, paper
oracle-admit | assertion | orchestrator | 1.00 | human, admission, study-type, graph.json
__changelog | meta | all | 1.00 | changes, version, index
::end

::node [id=banner type=meta confidence=1.00 scope=all updated=2026-11-09 entry=true skip-if-known=true]
::dense
academic|research|licensed-oversight|banner
::end
::warning
Read DISCLAIMER before any node.
::end
::edges
->[:precedes] protocol
::end
::end

::node [id=protocol type=meta confidence=1.00 scope=all updated=2026-11-09 skip-if-known=true]
::dense
search-index|resolve-context|llm-router|requires-loads|precedes-orders|dense-then-full
::end
::full
search_index reads this ::index and stops. Select one route id. resolve_context opens that Markdown index and follows :requires. A :precedes edge orders stages and does not load them. A :see-also edge does not load. ::dense is the second pass. ::full is the third. Read a terminal Markdown file only when the selected node names it. A ::warning is never skipped. skip-if-known loads once per session. A closed-list label stays closed until the task names it. Route stages are scope all. oracle-admit is scope orchestrator.
::end
::table
task | minimum read
read or rank rows | contract
resolve a key | contract → resolve-key
propose a pair | contract → resolve-key → propose-pairs
design | contract → falsify → pins → design → traces; bench → record → run
falsify | contract → falsify; the runtime is written outside the repository
traces | contract + traces → that runtime's trace judgement
seal a context tree | traces → seal
navigate | router
W004 | w004
::end
::note
Stop at the row's endpoint. Design continues to the sink. Source: docs/read-repository.md Indications. That file wins if this table differs.
::end
::reference
format: https://arxiv.org/html/2604.27820v1 retrieved 2026-11-09 (Australia/Sydney); HTML; no byte hash
::end
::edges
->[:see-also] read
->[:see-also] resolve
->[:see-also] propose
->[:see-also] falsify
->[:see-also] traces
->[:see-also] design
->[:see-also] router
->[:see-also] w004
->[:see-also] docs/read-repository.md
::end
::end

::node [id=law type=meta confidence=1.00 scope=all updated=2026-11-09 skip-if-known=true]
::dense
contract-governs|specbase-markdown|index-not-catalogue|oracle-open
::end
::warning
docs/follow-agent-contract.md governs. This index is not the specbase, not catalogue bytes, and not an admission.
::end
::edges
->[:see-also] docs/follow-agent-contract.md
::end
::end

::node [id=read type=route confidence=0.99 scope=all updated=2026-11-09]
::dense
read|rank|one-dictionary|pin-sha|absence
::end
::full
Open ooc/read.md. Endpoint is the contract.
::end
::edges
->[:requires] ooc/read.md
::end
::end

::node [id=resolve type=route confidence=0.99 scope=all updated=2026-11-09]
::dense
resolve|key|unresolved|unavailable|protein
::end
::full
Open ooc/resolve.md. Endpoint is skills/resolve-key.md.
::end
::edges
->[:requires] ooc/resolve.md
::end
::end

::node [id=propose type=route confidence=0.97 scope=all updated=2026-11-09]
::dense
propose|proposals.json|no-graph-write|no-study-type
::end
::full
Open ooc/propose.md. Endpoint is skills/propose-pairs.md.
::end
::edges
->[:requires] ooc/propose.md
::end
::end

::node [id=falsify type=route confidence=0.99 scope=all updated=2026-11-09]
::dense
falsify|attacks|workers|no-vote|outside-repo
::end
::full
Open ooc/falsify.md. Endpoint is docs/falsify.md.
::end
::edges
->[:requires] ooc/falsify.md
::end
::end

::node [id=traces type=route confidence=0.95 scope=all updated=2026-11-09]
::dense
trace|act-log|merkle|not-discharged
::end
::full
Open ooc/traces.md. Endpoint is systems/record-traces.md. The seal stage names systems/seal-og.md.
::end
::edges
->[:requires] ooc/traces.md
::end
::end

::node [id=design type=route confidence=0.95 scope=all updated=2026-11-09]
::dense
design|calibrate|epitope|worklist|sink
::end
::full
Open ooc/design.md. Endpoint is systems/run-campaign.md. Resolve one stage when the task names it.
::end
::edges
->[:requires] ooc/design.md
::end
::end

::node [id=oracle-open type=assertion confidence=1.00 scope=all updated=2026-11-09 skip-if-known=true]
::dense
predicate-16|not-discharged|no-automation
::end
::warning
Automation cannot discharge predicate 16.
::end
::assertion
trigger: after [read]
check: oracle == "not-discharged"
on-pass: ->[:proceed] read
on-fail: ->[:escalate] oracle-admit
::end
::end

::node [id=oracle-admit type=assertion confidence=1.00 scope=orchestrator updated=2026-11-09]
::dense
human-reads-paper|proposals.json|graph.json|study-type
::end
::full
Admission is a human reading the paper and moving a row from proposals.json into graph.json.
::end
::warning
Choosing pair versus preclinical is the oracle. An unread paper is not a default dictionary.
::end
::edges
->[:see-also] docs/follow-agent-contract.md
::end
::end

::node [id=router type=route confidence=0.99 scope=all updated=2026-11-09]
::dense
navigate|initialization|minimum-read|dag
::end
::full
Open docs/read-repository.md. Stop at the first sufficient row.
::end
::edges
->[:requires] docs/read-repository.md
::end
::end

::node [id=w004 type=route confidence=0.90 scope=all updated=2026-11-09]
::dense
w004|christmas|eveleigh|clinical-cost|talent
::end
::full
Open ooc/w004.md. Endpoint is docs/w004.md. The contract governs any sequence.
::end
::edges
->[:requires] ooc/w004.md
::end
::end

::node [id=__changelog type=meta confidence=1.00 scope=all updated=2026-11-09]
::changelog
2026-11-09|added|node [protocol]|traversal index over the Markdown specbase
2026-11-09|added|node [w004]|Christmas 2026 evening proposal
2026-11-09|added|node [router]|initialization route
2026-11-09|updated|node [traces]|seal stage for the context-tree root
::end
::end
