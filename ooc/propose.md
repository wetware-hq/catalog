::meta
title: Propose route
version: 1
updated: 2026-11-09
domain: catalog|propose|intake
scope: all
catalogue-version: 2
governs: docs/follow-agent-contract.md
checksum: sha256:8b3fc031017cb7f77c4b16857893fca7fd677a2b5cdaf0a7649dd7ad8c6db919
::end

::schema
node-types: [stage, assertion, meta]
edge-types: [requires, precedes, see-also]
scope-levels: [all, orchestrator, worker, readonly]
::end

::index
# id | type | scope | conf | keywords
banner | meta | all | 1.00 | academic, research, oversight, banner
minimum | stage | all | 0.97 | propose, intake, triple, recall, proposals
contract | stage | all | 1.00 | schema, proposal, add-only, serializer
resolve-key | stage | all | 0.99 | binder, target, unresolved, unavailable
propose-pairs | stage | all | 0.97 | enumerate, protein, pmid, deduplicate, writer
stop | assertion | all | 1.00 | endpoint, halt, sufficient
__changelog | meta | all | 1.00 | changes, version
::end

::node [id=banner type=meta confidence=1.00 scope=all updated=2026-11-09 entry=true skip-if-known=true]
::dense
academic|research|licensed-oversight
::end
::warning
Read DISCLAIMER before any node.
::end
::edges
->[:precedes] minimum
::end
::end

::node [id=minimum type=stage confidence=0.97 scope=all updated=2026-11-09]
::dense
propose|contract|resolve-key|propose-pairs|no-study-type
::end
::full
Cold start for intake. Stop at skills/propose-pairs.md.
::end
::warning
Never write graph.json. Never assign pair or preclinical. One writer appends proposals.json.
::end
::edges
->[:requires] docs/follow-agent-contract.md
->[:requires] skills/resolve-key.md
->[:requires] skills/propose-pairs.md
->[:precedes] stop
::end
::end

::node [id=contract type=stage confidence=1.00 scope=all updated=2026-11-09]
::dense
section-9|proposal-root|add-only|no-dictionary
::end
::full
Proposal shape and the file boundary.
::end
::edges
->[:requires] docs/follow-agent-contract.md
->[:precedes] resolve-key
::end
::end

::node [id=resolve-key type=stage confidence=0.99 scope=all updated=2026-11-09]
::dense
binder|target|exact-lookup|drop-unresolved
::end
::full
Resolve the triple before any append.
::end
::edges
->[:requires] skills/resolve-key.md
->[:precedes] propose-pairs
::end
::end

::node [id=propose-pairs type=stage confidence=0.97 scope=all updated=2026-11-09]
::dense
structured-authorities|recall-1|false-admit|refusal-ledger|single-writer
::end
::full
Endpoint of the propose route.
::end
::warning
A passing intake does not discharge predicate 16. Study type is chosen when a human reads the paper.
::end
::edges
->[:requires] skills/propose-pairs.md
->[:precedes] stop
::end
::end

::node [id=stop type=assertion confidence=1.00 scope=all updated=2026-11-09]
::dense
stop|endpoint|propose-pairs
::end
::assertion
trigger: after [propose-pairs]
check: endpoint("skills/propose-pairs.md")
on-pass: ->[:proceed] propose-pairs
on-fail: ->[:escalate] minimum
::end
::end

::node [id=__changelog type=meta confidence=1.00 scope=all updated=2026-11-09]
::changelog
2026-11-09|added|node [minimum]|propose route
::end
::end
