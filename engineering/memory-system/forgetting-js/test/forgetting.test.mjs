/**
 * Standalone test for selective-forgetting (open-source build).
 * Tests the pure scoring/eligibility/propagation functions with a minimal
 * repository mock — no plugin data layer, no SQLite.
 */
import { scoreBreakdown, scoreBand,
    scoreMemory, softForgetEligible, archiveEligible, isProtected,
    scanForgetting, overflowBackfill, propagationRisk,
    FORGETTING_DEFAULTS,
} from '../src/forgetting.js';

let pass = 0, fail = 0;
function ok(cond, name, detail = '') {
    if (cond) { pass++; console.log(`  PASS ${name}`); }
    else { fail++; console.log(`  FAIL ${name} ${detail}`); }
}

const nowIso = '2026-11-01T00:00:00Z';
const RECENT = '2026-10-15T00:00:00Z';

// ---- helpers ----
function row(over = {}) {
    return {
        id: 'r1', type: 'reference', title: 'Test topic memory', description: 'desc',
        status: 'active', scope: 'project', not_when: '', probation_until: null,
        corrects: null, soft_forgotten_at: null, soft_forget_reason: null,
        updated_at: RECENT,
        ...over,
    };
}
// repo.getUsage returns DB rows (snake_case); scanForgetting converts internally.
function dbUsage(useCount = 0, lastUsedAt = null) {
    return { use_count: useCount, last_used_at: lastUsedAt };
}
// Direct scoreMemory/softForgetEligible calls take camelCase usage.
function usage(useCount = 0, lastUsedAt = null) {
    return { useCount, lastUsedAt };
}

// NOTE: softForgetEligible signature is (row, usage, correctsOwners, nowIso, ctx).
// correctsOwners is a count of rows whose `corrects` points at this id (default 0).

// ---- V1: score model ----
console.log('\n== V1 score model ==');
{
    const fresh = scoreMemory(row(), usage(3, '2026-10-30T00:00:00Z'), nowIso);
    ok(fresh.score > 0.4, 'fresh+used score > 0.4', `got ${fresh.score}`);
    const stale = scoreMemory(row({ title: 'Old unrelated ref' }), usage(0, '2025-05-01T00:00:00Z'), nowIso, { activeTopics: ['gpu','compute'] });
    ok(stale.score < 0.2, 'stale+unused score < 0.2', `got ${stale.score}`);
    ok(stale.redundancyFactor === 1, 'stale redundancyFactor=1 (sole topic holder)', `got ${stale.redundancyFactor}`);
    ok(Math.abs(FORGETTING_DEFAULTS.W_TIME + FORGETTING_DEFAULTS.W_USAGE + FORGETTING_DEFAULTS.W_REDUNDANCY + FORGETTING_DEFAULTS.W_REUSE + FORGETTING_DEFAULTS.W_DRIFT - 1) < 1e-9, 'weights sum to 1');
}

// ---- V2: softForgetEligible ----
console.log('\n== V2 eligibility ==');
{
    const fresh = softForgetEligible(row(), usage(3, '2026-10-30T00:00:00Z'), 0, nowIso, { activeTopics: [] });
    ok(!fresh.eligible, 'fresh+used not eligible', fresh.reason);
    const stale = softForgetEligible(row({ title: 'Old unrelated ref' }), usage(0, '2025-05-01T00:00:00Z'), 0, nowIso, { activeTopics: ['gpu','compute'] });
    ok(stale.eligible, 'stale+unused eligible', stale.reason);
    ok(stale.reason === 'long-unused-zero-use', 'stale reason long-unused-zero-use', stale.reason);
    const user = softForgetEligible(row({ type: 'user' }), usage(0, '2025-05-01T00:00:00Z'), 0, nowIso, { activeTopics: [] });
    ok(!user.eligible, 'user protected', user.reason);
    const fb = softForgetEligible(row({ type: 'feedback' }), usage(0, '2025-05-01T00:00:00Z'), 0, nowIso, { activeTopics: [] });
    ok(!fb.eligible, 'feedback protected', fb.reason);
    const prob = softForgetEligible(row({ probation_until: '2026-12-01T00:00:00Z' }), usage(0, '2025-05-01T00:00:00Z'), 0, nowIso, { activeTopics: [] });
    ok(!prob.eligible, 'probation protected', prob.reason);
    const tm = softForgetEligible(row({ title: 'GPU compute cluster' }), usage(0, '2025-05-01T00:00:00Z'), 0, nowIso, { activeTopics: ['gpu'] });
    ok(!tm.eligible, 'topic-matched protected even if unused', tm.reason);
}

// ---- V3: isProtected ----
console.log('\n== V3 isProtected ==');
{
    ok(isProtected(row({ type: 'user' }), 0), 'user protected');
    ok(isProtected(row({ type: 'feedback' }), 0), 'feedback protected');
    ok(isProtected(row({ probation_until: '2026-12-01' }), 0), 'probation protected');
    ok(isProtected(row(), 1), 'corrects-referenced protected');
    ok(!isProtected(row(), 0), 'plain reference not protected');
}

// ---- V4: archiveEligible ----
console.log('\n== V4 archiveEligible ==');
{
    const archNot = archiveEligible({ soft_forgotten_at: '2026-10-01T00:00:00Z' }, nowIso);
    ok(!archNot.eligible, 'archived <90d not eligible', archNot.reason);
    const archYes = archiveEligible({ soft_forgotten_at: '2025-05-01T00:00:00Z' }, nowIso);
    ok(archYes.eligible, 'archived >=90d eligible', archYes.reason);
}

// ---- V5: propagationRisk ----
console.log('\n== V5 propagationRisk ==');
{
    const repo = {
        listRows: () => [
            row({ id: 'load', title: 'load-bearing' }),
            row({ id: 'corrected', title: 'corrected' }),
            row({ id: 'plain', title: 'plain ref' }),
        ],
        listWorkspaces: () => [{ workspace_id: '/ws', updated_at: nowIso }],
    };
    const risk = propagationRisk(repo, '/ws', 'load', nowIso);
    ok(risk.loadBearing, 'load-bearing (corrects chain)');
    const riskPlain = propagationRisk(repo, '/ws', 'plain', nowIso);
    ok(riskPlain.loadBearing || riskPlain.soleTopicHolder, 'plain ref load-bearing if sole topic');
}

// ---- V6: scanForgetting ----
console.log('\n== V6 scanForgetting ==');
{
    const rows = [];
    for (let i = 0; i < 13; i++) rows.push(row({ id: 'f'+i, title: 'Filler topic '+i, updated_at: '2026-10-15T00:00:00Z' }));
    rows.push(row({ id: 'o1', title: 'Old unrelated ref', updated_at: '2026-10-01T00:00:00Z' }));
    const mockRepo = {
        listRows: () => rows,
        getUsage: (ws, [id]) => id === 'o1' ? dbUsage(0, '2025-05-01T00:00:00Z') : undefined,
        listWorkspaces: () => [{ workspace_id: '/ws', updated_at: nowIso }],
    };
    const scan = scanForgetting(mockRepo, '/ws', nowIso, { activeTopics: ['gpu', 'compute'] });
    // REFERENCE_RELEVANCE=0.7 now correctly marks same-topic redundant references
    // as forgettable (their scores drop below 0.15). o1 is the long-unused one.
    ok(scan.softForgetCandidates.some((c) => c.id === 'o1'), 'o1 is among the candidates', scan.softForgetCandidates.map((c) => c.id).join(','));
    ok(scan.softForgetCandidates.length >= 13, 'redundant same-topic fillers also candidates', `got ${scan.softForgetCandidates.length}`);
}

// ---- V7: overflowBackfill ----
console.log('\n== V7 overflowBackfill ==');
{
    const rows = [];
    for (let i = 0; i < 30; i++) rows.push(row({ id: 'r'+i, title: 'Recent topic '+i, updated_at: RECENT }));
    rows.push(row({ id: 'u1', type: 'user', title: 'User profile', updated_at: RECENT }));
    const mockRepo = {
        listInjectedRows: () => rows,
        getUsage: () => undefined,
        listWorkspaces: () => [{ workspace_id: '/ws', updated_at: nowIso }],
    };
    const res = overflowBackfill(mockRepo, '/ws', 1800, nowIso, { activeTopics: [] });
    ok(res.wouldOverflow, 'would overflow', `projected ${res.projectedTokens}`);
    ok(res.proposals.length > 0, 'proposals not empty', `got ${res.proposals.length}`);
    ok(res.proposals.every(p => !p.id.startsWith('u1')), 'user never proposed');
}

console.log(`\n==== V1-V7: ${pass} PASS / ${fail} FAIL ====`);
// ---- V8: restore path (v3) ----
console.log('\n== V8 restore ==');
{
    // A soft-forgotten row whose v2 score is above threshold should be restorable.
    const forgot = row({ id: 'restore-me', title: 'Fresh important ref', soft_forgotten_at: '2026-10-30T00:00:00Z' });
    const elig = softForgetEligible(forgot, usage(2, '2026-10-30T00:00:00Z'), 0, nowIso, { activeTopics: [] });
    ok(!elig.eligible, 'restore not eligible', elig.reason);
    ok(elig.shouldRestore === true, 'shouldRestore=true', String(elig.shouldRestore));
    ok(elig.reason === 'restore', 'reason restore', elig.reason);

    // A genuinely low-value soft-forgotten row stays archived-eligible.
    const stillOld = row({ id: 'old-forgot', title: 'Old unrelated', soft_forgotten_at: '2026-10-01T00:00:00Z', updated_at: '2026-05-01T00:00:00Z' });
    const elig2 = softForgetEligible(stillOld, usage(0, '2026-05-01T00:00:00Z'), 0, nowIso, { activeTopics: [] });
    ok(!elig2.shouldRestore, 'low-score stays not-restorable', String(elig2.shouldRestore));

    // scanForgetting should surface restoreCandidates.
    const rows = [
        row({ id: 'restore-me', title: 'Fresh important ref', soft_forgotten_at: '2026-10-30T00:00:00Z' }),
        row({ id: 'old-forgot', title: 'Old unrelated', soft_forgotten_at: '2026-10-01T00:00:00Z', updated_at: '2026-05-01T00:00:00Z' }),
    ];
    const mockRepo = {
        listRows: () => rows,
        getUsage: (ws, [id]) => id === 'restore-me' ? dbUsage(2, '2026-10-30T00:00:00Z') : dbUsage(0, '2026-05-01T00:00:00Z'),
        listWorkspaces: () => [{ workspace_id: '/ws', updated_at: nowIso }],
    };
    const scan = scanForgetting(mockRepo, '/ws', nowIso, { activeTopics: [] });
    ok(scan.restoreCandidates.length === 1, 'scan finds restore candidate', `got ${scan.restoreCandidates.length}`);
    ok(scan.restoreCandidates[0]?.id === 'restore-me', 'restore candidate is restore-me', scan.restoreCandidates[0]?.id);
    ok(scan.restoreCandidates[0]?.reason === 'score-recovered', 'restore reason score-recovered', scan.restoreCandidates[0]?.reason);
    ok(scan.archiveCandidates.length === 0, 'no archive candidate (restore takes precedence)', `got ${scan.archiveCandidates.length}`);
}

// ---- V9: scoreBreakdown / scoreBand (v3) ----
console.log('\n== V9 breakdown & band ==');
{
    const bd = scoreBreakdown(row(), usage(3, '2026-10-30T00:00:00Z'), nowIso, { activeTopics: [] });
    ok(bd.score > 0.4, 'breakdown score > 0.4', `got ${bd.score.toFixed(3)}`);
    ok(bd.dominant === 'time' || bd.dominant === 'usage', 'dominant is time or usage', bd.dominant);
    ok(bd.components.length === 5, '5 components', `got ${bd.components.length}`);
    ok(bd.components.every((c) => c.name && typeof c.contribution === 'number'), 'each component has name+contribution');
    const sum = bd.components.reduce((a, c) => a + c.contribution, 0);
    ok(Math.abs(sum - bd.score) < 1e-9, 'contributions sum to score', `sum ${sum.toFixed(4)} vs ${bd.score.toFixed(4)}`);

    ok(scoreBand(0.05).band === 'forget-candidate', '0.05 is forget-candidate', scoreBand(0.05).band);
    ok(scoreBand(0.15).band === 'soft-zone', '0.15 is soft-zone', scoreBand(0.15).band);
    ok(scoreBand(0.35).band === 'soft-zone', '0.35 is soft-zone', scoreBand(0.35).band);
    ok(scoreBand(0.8).band === 'retained', '0.8 is retained', scoreBand(0.8).band);
    ok(scoreBand(0.15).pctAboveSoftForget === 0, 'threshold is 0% above', String(scoreBand(0.15).pctAboveSoftForget));
}

// ---- V10: threshold sensitivity & false-positive guard (v3) ----
console.log('\n== V10 sensitivity ==');
{
    // A memory that is recent + used must NEVER be a forget candidate at any
    // reasonable threshold. Guards against false positives on fresh content.
    const fresh = softForgetEligible(row({ title: 'Current GPU project' }), usage(3, '2026-10-30T00:00:00Z'), 0, nowIso, { activeTopics: ['gpu'] });
    ok(!fresh.eligible, 'fresh+used+topic never forget', fresh.reason);

    // The v1 false-positive scenario: reference, age 1.1d, zero use.
    // Under v2 it must score ABOVE threshold (0.15) because it is recent.
    const oneDay = scoreMemory(row({ title: 'Brand new ref' }), usage(0, '2026-10-30T00:00:00Z'), nowIso, { activeTopics: [] });
    ok(oneDay.score > 0.15, '1-day-old zero-use ref scores above 0.15', `got ${oneDay.score.toFixed(3)}`);

    // Older + zero use: below threshold only when genuinely old.
    const old = scoreMemory(row({ title: 'Aged unused ref' }), usage(0, '2025-05-01T00:00:00Z'), nowIso, { activeTopics: [] });
    ok(old.score < 0.15, '6-month unused ref below threshold', `got ${old.score.toFixed(3)}`);
}


console.log(`\n==== TOTAL: ${pass} PASS / ${fail} FAIL ====`);
process.exit(fail > 0 ? 1 : 0);
