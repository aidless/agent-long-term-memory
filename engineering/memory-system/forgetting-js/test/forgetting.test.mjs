/**
 * Standalone test for selective-forgetting (open-source build).
 * Tests the pure scoring/eligibility/propagation functions with a minimal
 * repository mock — no plugin data layer, no SQLite.
 */
import {
    scoreMemory, softForgetEligible, archiveEligible, isProtected,
    scanForgetting, overflowBackfill, propagationRisk,
    FORGETTING_DEFAULTS,
} from '../src/forgetting/forgetting.js';

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
    ok(scan.softForgetCandidates.length === 1, 'scan finds only o1', `got ${scan.softForgetCandidates.length}`);
    ok(scan.softForgetCandidates[0]?.id === 'o1', 'o1 is the candidate', scan.softForgetCandidates[0]?.id);
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

console.log(`\n==== ${pass} PASS / ${fail} FAIL ====`);
process.exit(fail > 0 ? 1 : 0);
