/**
 * Standalone test for selective-forgetting (open-source build).
 * Tests the pure scoring/eligibility/propagation functions with a minimal
 * repository mock — no plugin data layer, no SQLite.
 */
import { scoreBreakdown, scoreBand,
    scoreMemory, softForgetEligible, archiveEligible, isProtected,
    scanForgetting, overflowBackfill, propagationRisk,
    unarchiveEligible, scanUnarchive,
    updatePotential, diversityModulation, tieredForgetRate,
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
    ok(Math.abs(FORGETTING_DEFAULTS.W_TIME + FORGETTING_DEFAULTS.W_USAGE + FORGETTING_DEFAULTS.W_REDUNDANCY + FORGETTING_DEFAULTS.W_REUSE + FORGETTING_DEFAULTS.W_DRIFT + FORGETTING_DEFAULTS.W_POTENTIAL - 1) < 1e-9, 'weights sum to 1');
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
    for (let i = 0; i < 13; i++) rows.push(row({ id: 'f'+i, title: 'Filler topic '+i, updated_at: '2026-07-01T00:00:00Z' }));
    rows.push(row({ id: 'o1', title: 'Old unrelated ref', updated_at: '2025-01-01T00:00:00Z' }));
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
    ok(bd.components.length === 6, '6 components', `got ${bd.components.length}`);
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


// ---- V11: un-archive re-evaluation (v4) ----
console.log('\n== V11 unarchive ==');
{
    // An archived row re-used since archiving must be restored.
    const reused = unarchiveEligible(
        { id: 'arch-reused', type: 'reference', title: 'Old but reused', status: 'archived' },
        { useCount: 2, lastUsedAt: '2026-10-30T00:00:00Z' },
        nowIso, {}
    );
    ok(reused.eligible === true, 'archived+reused is un-archive eligible', reused.reason);
    ok(reused.reason === 'reused-since-archive', 'reused reason is reused-since-archive', reused.reason);

    // An archived row with high score (recovered) must be restored.
    const high = unarchiveEligible(
        { id: 'arch-high', type: 'user', title: 'High value recent', status: 'archived', updated_at: '2026-10-30T00:00:00Z' },
        { useCount: 0, lastUsedAt: null },
        nowIso, {}
    );
    ok(high.eligible === true, 'archived+high-score is un-archive eligible', high.reason);

    // A truly dead archived row stays archived.
    const dead = unarchiveEligible(
        { id: 'arch-dead', type: 'reference', title: 'Dead old ref', status: 'archived', updated_at: '2025-05-01T00:00:00Z' },
        { useCount: 0, lastUsedAt: null },
        nowIso, {}
    );
    ok(dead.eligible === false, 'archived+dead stays archived', dead.reason);
    ok(dead.reason === 'score-low', 'dead reason is score-low', dead.reason);

    // A merged duplicate (superseded by a newer version) NEVER comes back,
    // even with a high score — the replacement is canonical.
    const merged = unarchiveEligible(
        { id: 'arch-merged', type: 'user', title: 'Old version', status: 'archived', updated_at: '2026-10-30T00:00:00Z', merged_into: 'new-version' },
        { useCount: 0, lastUsedAt: null },
        nowIso, {}
    );
    ok(merged.eligible === false, 'merged duplicate never un-archives', merged.reason);
    ok(merged.reason === 'merged-superseded', 'merged reason is merged-superseded', merged.reason);

    // scanUnarchive end-to-end with a mock repo.
    const repo = {
        listArchivedRows: () => [
            { id: 'a1', type: 'reference', title: 'Reused archived', status: 'archived', updated_at: '2026-10-30T00:00:00Z' },
            { id: 'a2', type: 'reference', title: 'Dead archived', status: 'archived', updated_at: '2025-05-01T00:00:00Z' },
        ],
        getUsage: (ws, [id]) => id === 'a1'
            ? { use_count: 1, last_used_at: '2026-10-30T00:00:00Z' }
            : { use_count: 0, last_used_at: null },
    };
    const scan = scanUnarchive(repo, '/ws', nowIso, {});
    ok(scan.unarchiveCandidates.length === 1, 'scanUnarchive finds exactly 1', String(scan.unarchiveCandidates.length));
    ok(scan.unarchiveCandidates[0].id === 'a1', 'unarchive candidate is a1', scan.unarchiveCandidates[0]?.id);
    ok(scan.scanned.length === 2, 'scanUnarchive scans 2 rows', String(scan.scanned.length));
}


// ---- V12: adversarial robustness (v4) ----
console.log('\n== V12 adversarial ==');
{
    const now = '2026-11-01T00:00:00Z';
    const ctx = { activeTopics: [] };
    const base = { id: 'x', title: 'test', type: 'reference', status: 'active' };
    const cases = [
        ['null usage', base, null],
        ['empty usage', base, {}],
        ['NaN use', base, { useCount: NaN, lastUsedAt: now }],
        ['negative use', base, { useCount: -5, lastUsedAt: now }],
        ['huge use', base, { useCount: 1e9, lastUsedAt: now }],
        ['malformed date', base, { useCount: 1, lastUsedAt: 'not-a-date' }],
        ['future date', base, { useCount: 0, lastUsedAt: '2099-01-01T00:00:00Z' }],
        ['empty title', { ...base, title: '' }, { useCount: 0, lastUsedAt: now }],
        ['undefined params', base, { useCount: 0, lastUsedAt: now }, undefined],
    ];
    for (const [name, row, usage, params] of cases) {
        let s;
        try {
            s = scoreMemory(row, usage, now, ctx, params);
        } catch (e) {
            fail++; console.log(`  FAIL ${name}: threw ${e.message}`); continue;
        }
        if (Number.isFinite(s.score) && s.score >= 0 && s.score <= 1) {
            pass++;
        } else {
            fail++; console.log(`  FAIL ${name}: score=${s.score}`);
        }
    }
    // Extreme weight vectors must not produce NaN / out-of-range scores.
    const wCases = [
        ['all zero weights', { W_TIME: 0, W_USAGE: 0, W_REDUNDANCY: 0, W_REUSE: 0, W_DRIFT: 0 }],
        ['all one weights', { W_TIME: 1, W_USAGE: 1, W_REDUNDANCY: 1, W_REUSE: 1, W_DRIFT: 1 }],
        ['time only', { W_TIME: 1, W_USAGE: 0, W_REDUNDANCY: 0, W_REUSE: 0, W_DRIFT: 0 }],
    ];
    for (const [name, p] of wCases) {
        const s = scoreMemory(base, { useCount: 0, lastUsedAt: now }, now, ctx, p);
        if (Number.isFinite(s.score) && s.score >= 0 && s.score <= 1) {
            pass++;
        } else {
            fail++; console.log(`  FAIL ${name}: score=${s.score}`);
        }
    }
    // unarchiveEligible with NaN / null usage must not throw or misjudge.
    const uCases = [
        [{ ...base, status: 'archived' }, null],
        [{ ...base, status: 'archived' }, { useCount: NaN, lastUsedAt: now }],
    ];
    for (const [row, usage] of uCases) {
        let u;
        try {
            u = unarchiveEligible(row, usage, now, {});
        } catch (e) {
            fail++; console.log(`  FAIL unarchive threw: ${e.message}`); continue;
        }
        if (typeof u.eligible === 'boolean') {
            pass++;
        } else {
            fail++; console.log(`  FAIL unarchive eligible=${u.eligible}`);
        }
    }
}


// ---- V13: evidence-weighted usage shrink (v5) ----
console.log('\n== V13 evidence-weighted shrink ==');
{
    const now = '2026-11-01T00:00:00Z';
    const ctx = { activeTopics: [] };
    const base = { id: 'ev', title: 'evidence', type: 'reference', status: 'active' };
    const expectClose = (got, want, name, eps = 1e-9) => {
        if (Math.abs(got - want) <= eps) { pass++; }
        else { fail++; console.log(`  FAIL ${name}: got ${got}, want ${want}`); }
    };
    // use=0: usageFactor stays 0 (no evidence -> continue forgettable).
    const s0 = scoreMemory(base, { useCount: 0, lastUsedAt: now }, now, ctx);
    expectClose(s0.usageFactor, 0, 'use=0 keeps usageFactor 0');
    // use=1: linear=1/3, shrink=1/3 -> 0.5 + (0.333-0.5)*0.333 = 0.444 (shrunk toward 0.5).
    const s1 = scoreMemory(base, { useCount: 1, lastUsedAt: now }, now, ctx);
    expectClose(s1.usageFactor, 0.5 + (1/3 - 0.5) * (1/3), 'use=1 shrinks toward 0.5');
    // use=2: linear=2/3, shrink=1/2 -> 0.5 + (0.667-0.5)*0.5 = 0.583 (shrunk toward 0.5).
    const s2 = scoreMemory(base, { useCount: 2, lastUsedAt: now }, now, ctx);
    expectClose(s2.usageFactor, 0.5 + (2/3 - 0.5) * (1/2), 'use=2 shrinks toward 0.5');
    // use=3: linear=1, shrink=3/5 -> 0.5 + 0.5*0.6 = 0.8 (approaching linear).
    const s3 = scoreMemory(base, { useCount: 3, lastUsedAt: now }, now, ctx);
    expectClose(s3.usageFactor, 0.5 + 0.5 * (3/5), 'use=3 approaches linear');
    // Monotonic: usageFactor(0) < usageFactor(1) < usageFactor(2) < usageFactor(3).
    if (s0.usageFactor < s1.usageFactor && s1.usageFactor < s2.usageFactor && s2.usageFactor < s3.usageFactor) {
        pass++;
    } else {
        fail++; console.log('  FAIL usageFactor not monotonic in useCount');
    }
    // Bounded: 0 <= usageFactor <= 1 for all use counts.
    for (const u of [0, 1, 2, 3, 10, 100]) {
        const s = scoreMemory(base, { useCount: u, lastUsedAt: now }, now, ctx);
        if (s.usageFactor >= 0 && s.usageFactor <= 1) { pass++; }
        else { fail++; console.log(`  FAIL use=${u} usageFactor=${s.usageFactor} out of range`); }
    }
    // Large use -> approaches linear 1.
    const sBig = scoreMemory(base, { useCount: 1000, lastUsedAt: now }, now, ctx);
    expectClose(sBig.usageFactor, 1, 'use=1000 approaches linear 1', 1e-3);
}


// ---- V14: survival potential dynamics (v6, SF-AMS Eq.3) ----
console.log('\n== V14 survival potential ==');
{
    // Fresh memory, not used, low importance: decays toward floor.
    let phi = updatePotential(0, 0.5, false, 1);
    ok(phi === Math.max(0, 0 - FORGETTING_DEFAULTS.POTENTIAL_DECAY), 'unused decays by lambda', `got ${phi}`);
    // Used + important: rises.
    const before = 0.3;
    const after = updatePotential(before, 0.8, true, 1);
    ok(after > before, 'used+important raises potential', `got ${after}`);
    ok(Math.abs(after - (before + 0.8 - FORGETTING_DEFAULTS.POTENTIAL_DECAY)) < 1e-9, 'exact increment', `got ${after}`);
    // Used + low importance: still may rise if importance > decay.
    const low = updatePotential(0.2, 0.1, true, 1);
    ok(Math.abs(low - (0.2 + 0.1 - FORGETTING_DEFAULTS.POTENTIAL_DECAY)) < 1e-9, 'low importance used', `got ${low}`);
    // Never goes below floor.
    const floor = updatePotential(0.01, 0.1, false, 1);
    ok(floor === 0, 'floored at 0', `got ${floor}`);
    // Diversity modulation: novel (sim < tau) boosts, redundant (sim > tau) dampens.
    const novel = updatePotential(0.5, 0.8, true, diversityModulation(0.2));
    const redundant = updatePotential(0.5, 0.8, true, diversityModulation(0.9));
    ok(novel > redundant, 'novel memory gets more reinforcement than redundant', `novel=${novel} redundant=${redundant}`);
    // Adversarial: NaN inputs do not poison.
    const nanPot = updatePotential(NaN, NaN, true, NaN);
    ok(Number.isFinite(nanPot), 'NaN inputs produce finite potential', `got ${nanPot}`);
    // diversityModulation neutral at similarity = tau.
    const neutral = diversityModulation(FORGETTING_DEFAULTS.DIVERSITY_TAU);
    ok(Math.abs(neutral - 1) < 1e-9, 'neutral at sim=tau', `got ${neutral}`);
    // Bounded: phi never exceeds a sane ceiling (importance<=1, div<=1+alpha).
    const cap = updatePotential(5, 1, true, 1 + FORGETTING_DEFAULTS.DIVERSITY_ALPHA);
    ok(Number.isFinite(cap) && cap <= 5 + 1.5, 'bounded accumulation', `got ${cap}`);
}

// ---- V15: tiered forgetting rate (v6, SF-AMS Table 4) ----
console.log('\n== V15 tiered forgetting ==');
{
    // Tier 1 (core): score >= 0.80 -> never forgotten.
    const core = tieredForgetRate(0.93);
    ok(core.tier === 1 && core.forgetRate === 0, 'core tier forgetRate=0', JSON.stringify(core));
    // Tier 2 (important): score in [0.60, 0.80).
    const imp = tieredForgetRate(0.745);
    ok(imp.tier === 2 && Math.abs(imp.forgetRate - 0.1485) < 1e-9, 'important tier rate=0.1485', JSON.stringify(imp));
    // Tier 3 (secondary): score in [threshold, 0.60).
    const sec = tieredForgetRate(0.546);
    ok(sec.tier === 3 && Math.abs(sec.forgetRate - 0.3983) < 1e-9, 'secondary tier rate=0.3983', JSON.stringify(sec));
    // Tier 4 (irrelevant): score < threshold.
    const irr = tieredForgetRate(0.10);
    ok(irr.tier === 4 && Math.abs(irr.forgetRate - 0.6474) < 1e-9, 'irrelevant tier rate=0.6474', JSON.stringify(irr));
    // Monotonic: forget rate strictly increases as tier goes down.
    const rates = [core.forgetRate, imp.forgetRate, sec.forgetRate, irr.forgetRate];
    ok(rates.every((r, i) => i === 0 || r > rates[i - 1]), 'forget rate increases down tiers', rates.join(','));
    // Adversarial: NaN score -> treated as irrelevant (safest).
    const nanTier = tieredForgetRate(NaN);
    ok(nanTier.tier === 4, 'NaN score -> irrelevant tier', JSON.stringify(nanTier));
    // Score with potential dimension: a high-potential memory is retained.
    const potBase = { id: 'pot', title: 'potential', type: 'reference', status: 'active' };
    const potCtx = { activeTopics: [], potential: 0.9 };
    const highPot = scoreMemory(potBase, { useCount: 2, lastUsedAt: nowIso }, nowIso, potCtx);
    ok(highPot.score > 0.4, 'high potential retains score', `got ${highPot.score.toFixed(3)}`);
    // Score with zero potential: lower than with high potential.
    const lowPotCtx = { activeTopics: [], potential: 0 };
    const lowPot = scoreMemory(potBase, { useCount: 2, lastUsedAt: nowIso }, nowIso, lowPotCtx);
    ok(lowPot.score < highPot.score, 'zero potential scores lower', `low=${lowPot.score.toFixed(3)} high=${highPot.score.toFixed(3)}`);
}

// ---- V16: tier-driven soft-forget probability (v7 direction ②) ----
console.log('\n== V16 tier-driven soft-forget ==');
{
    // Build a workspace of 30 low-score (irrelevant tier 4) memories.
    const wsId = 'ws-tier';
    const tierRows = Array.from({ length: 30 }, (_, i) => ({
        id: `t${i}`, title: `low${i}`, body: '', description: '', type: 'reference',
        status: 'active', soft_forgotten_at: null, updated_at: '2026-01-01T00:00:00Z',
        useCount: 0, score: 0.05, potential: 0.5,
    }));
    const tierRepo = {
        listRows: () => tierRows,
        getUsage: (ws, ids) => {
            const r = tierRows.find((x) => x.id === (ids?.[0] ?? ws));
            return r ? { use_count: 0, last_used_at: null } : { use_count: 0, last_used_at: null };
        },
    };
    // When TIER_DRIVES_SOFT_FORGET is off (default), every candidate is admitted.
    const off = scanForgetting(tierRepo, wsId, nowIso, { MIN_ACTIVE: 1 });
    ok(off.softForgetCandidates.length === 30, 'default admits all candidates', `got ${off.softForgetCandidates.length}`);
    ok(off.softForgetCandidates.every((c) => c.tier === 4), 'candidates carry tier=4', JSON.stringify(off.softForgetCandidates[0]));
    // When on, admission is probabilistic near the tier-4 forgetRate (0.6474).
    // 30 candidates × 60 runs gives a stable estimate.
    let admitted = 0, trials = 0;
    for (let run = 0; run < 60; run++) {
        const on = scanForgetting(tierRepo, wsId, nowIso, { MIN_ACTIVE: 1, TIER_DRIVES_SOFT_FORGET: true });
        admitted += on.softForgetCandidates.length;
        trials += tierRows.length;
    }
    const rate = admitted / trials;
    ok(rate > 0.55 && rate < 0.75, `probabilistic admission near tier-4 rate (got ${(rate * 100).toFixed(1)}%)`, `admitted ${admitted}/${trials}`);
    // A tier-2 (important) memory is admitted far less often than tier-4.
    const impRows = [{
        id: 'imp', title: 'important', body: '', description: '', type: 'reference',
        status: 'active', soft_forgotten_at: null, updated_at: '2026-10-15T00:00:00Z',
        useCount: 1, score: 0.745, potential: 0.5,
    }];
    const impRepo = {
        listRows: () => impRows,
        getUsage: (ws, ids) => ({ use_count: 1, last_used_at: null }),
    };
    let impAdmitted = 0;
    for (let run = 0; run < 60; run++) {
        const on = scanForgetting(impRepo, wsId, nowIso, { MIN_ACTIVE: 0, TIER_DRIVES_SOFT_FORGET: true });
        if (on.softForgetCandidates.length > 0) impAdmitted++;
    }
    ok(impAdmitted < 20, `tier-2 admitted less often (got ${impAdmitted}/60)`, `expected < 20/60 (~14.9%)`);
}


console.log(`\n==== TOTAL: ${pass} PASS / ${fail} FAIL ====`);
process.exit(fail > 0 ? 1 : 0);
