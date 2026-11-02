/**
 * Selective forgetting for the memory store (v2 — multi-dimensional).
 *
 * The core claim: a memory system that selectively forgets beats one that only
 * accumulates. Forgetting is NOT information loss — it is budget reallocation.
 * A low-score memory is demoted out of the per-session injection list (soft
 * forget) but stays searchable and recoverable; only after it remains unused
 * for a long window does it archive (still recoverable via review).
 *
 * v2 score model (weighted multi-dimensional):imensional):
 *   score = W_TIME * time_factor + W_USAGE * usage_factor
 *         + W_REDUNDANCY * redundancy_factor + W_REUSE * reuse_factor
 *         + W_DRIFT * drift_factor
 *
 * Dimensions:
 *   - time:       Ebbinghaus decay since last use
 *   - usage:      use frequency (saturated at USAGE_SATURATION)
 *   - redundancy: topic-cluster crowding (same-topic siblings lower the score)
 *   - reuse:      cross-workspace / cross-project value
 *   - drift:      topic drift away from active work (contextual importance)
 *
 * Protection rules (hard-coded, never forgotten):
 *   - type='user'    (identity / profile / preference)
 *   - type='feedback' (correction history)
 *   - probation_until non-null (trial)
 *   - referenced by another memory's `corrects`  (load-bearing chain)
 *   - active count at MIN_ACTIVE floor           (stop forgetting)
 *   - topic-matched (active work context)         (v2 contextual importance)
 */

/** Tuning parameters. Overridable via plugin config later. */
export const FORGETTING_DEFAULTS = {
    /** use_count at which the usage factor saturates (no further boost). */
    USAGE_SATURATION: 3,
    /** Ebbinghaus decay rate per day (half-life ≈ ln2/λ ≈ 14 days at 0.05). */
    DECAY_RATE: 0.05,
    /** Relevance factor floor for forgettable types (reference). */
    REFERENCE_RELEVANCE: 0.7,
    /** Days since last use (or creation) before a zero-use memory is soft-forgettable. */
    SOFT_FORGET_DAYS: 45,
    /** Score below which a memory becomes a soft-forget candidate. */
    SOFT_FORGET_SCORE: 0.15,
    /** Days a soft-forgotten memory may stay demoted before archiving. */
    ARCHIVE_DAYS: 90,
    /** Minimum active rows to keep (never forget below this). */
    MIN_ACTIVE: 12,
    /** Projected per-line cost for the overflow-backfill trigger. */
    PROJECTED_LINE_TOKENS: 70,
    // When overflow backfill finds no memory below the soft-forget threshold
    // but the budget is still exceeded, it may demote the lowest-scoring rows
    // regardless of score. This is the "budget pressure" escape hatch — it
    // only fires when the projected cost exceeds the budget by this fraction,
    // so a marginal overflow does not evict healthy memories.
    OVERFLOW_EVICTION_FRACTION: 1.15,

    // === v2 multi-dimensional weights (sum to 1.0) ===
    /** Weight of temporal decay (long unused). */
    W_TIME: 0.40,
    /** Weight of usage frequency. */
    W_USAGE: 0.23,
    /** Weight of content redundancy (same-topic cluster). */
    W_REDUNDANCY: 0.14,
    /** Weight of cross-project reuse value. */
    W_REUSE: 0.05,
    /** Weight of topic drift vs. active projects. */
    W_DRIFT: 0.08,
    /** Weight of survival potential (v6, SF-AMS Eq.3). */
    W_POTENTIAL: 0.10,
    /** How many same-topic siblings make a memory redundant. */
    REDUNDANCY_SATURATION: 3,
    /** A memory referenced by other workspaces/projects gets a reuse boost. */
    REUSE_BOOST: 1.0,
    /** Topic match bonus for memories whose keywords hit active project topics. */
    TOPIC_MATCH_BONUS: 1.0,
    /** Score above which an archived memory is worth un-archiving (re-evaluated). */
    UNARCHIVE_SCORE: 0.5,
    /** Use-count at which the evidence-weighted usage factor is half-shrunk. */
    EVIDENCE_HALF: 2,

    // === v6 survival potential dynamics (SF-AMS Eq.3) ===
    /** Global decay coefficient λ: how fast a memory's potential decays per patrol. */
    POTENTIAL_DECAY: 0.02,
    /** Weight of the survival-potential dimension in the composite score. */
    W_POTENTIAL: 0.10,
    /** Diversity modulation strength α_div in Ψ_div (SF-AMS Eq.4). */
    DIVERSITY_ALPHA: 0.5,
    /** Similarity threshold τ in Ψ_div: below it a memory is "novel" (boosted). */
    DIVERSITY_TAU: 0.7,
    /** Transition sharpness β in Ψ_div (higher = sharper gating). */
    DIVERSITY_BETA: 5.0,
    /** Floor for the survival potential (a long-unused memory never goes negative). */
    POTENTIAL_FLOOR: 0,
};

/**
 * Days between two ISO timestamps (or "now" when only one is given).
 * @param iso - An ISO timestamp.
 * @param nowIso - The reference instant (defaults to now).
 * @returns Whole days, >= 0.
 */
function daysSince(iso, nowIso) {
    if (!iso) {
        return Number.MAX_SAFE_INTEGER;
    }
    const then = Date.parse(iso);
    if (Number.isNaN(then)) {
        return Number.MAX_SAFE_INTEGER;
    }
    const now = nowIso ? Date.parse(nowIso) : Date.now();
    return Math.max(0, Math.floor((now - then) / 86400000));
}

/**
 * Compute one memory's forget score (v2 multi-dimensional).
 *
 * v2 replaces the single-product model with a weighted sum of independent
 * dimensions. Each dimension measures a different failure mode, so a memory
 * that is merely old (but heavily reused) is NOT forgotten, and a memory that
 * is fresh but redundant (a duplicate of a same-topic sibling) IS a candidate.
 *
 *   score = W_TIME * time_factor
 *         + W_USAGE * usage_factor
 *         + W_REDUNDANCY * redundancy_factor
 *         + W_REUSE * reuse_factor
 *         + W_DRIFT * drift_factor
 *
 * @param row - A memories row (snake_case columns).
 * @param usage - `{ useCount, lastUsedAt } | undefined` from memory_usage.
 * @param nowIso - Reference instant for deterministic tests.
 * @param ctx - Context for the extra dimensions:
 *   - `sameTopicCount`: number of active siblings in the same topic cluster.
 *   - `crossWorkspaceRefs`: times this memory is referenced from other workspaces.
 *   - `activeTopics`: array of topic keywords for currently active projects.
 *   - `potential`: the stored survival potential Φ(t) ∈ [0,1] (v6; optional).
 *   - `similarity`: max semantic similarity to a sibling ∈ [0,1] (v6; optional).
 * @param params - Overrides for the defaults.
 * @returns The score in [0, 1], plus the dimension factors for diagnostics.
 */

/**
 * Human-readable breakdown of a memory's v2 score.
 * @param row - A memories row.
 * @param usage - `{ useCount, lastUsedAt } | undefined`.
 * @param nowIso - Reference instant.
 * @param ctx - Context for extra dimensions (see scoreMemory).
 * @param params - Overrides.
 * @returns `{ score, components, dominant, verdict }` where `dominant` names the
 *          dimension contributing most to the score and `verdict` is a
 *          human-readable one-liner for the diagnostic log.
 */
export function scoreBreakdown(row, usage, nowIso, ctx = {}, params = {}) {
    const d = scoreMemory(row, usage, nowIso, ctx, params);
    const components = [
        { name: "time", value: d.timeFactor, weight: (params.W_TIME ?? FORGETTING_DEFAULTS.W_TIME) },
        { name: "usage", value: d.usageFactor, weight: (params.W_USAGE ?? FORGETTING_DEFAULTS.W_USAGE) },
        { name: "redundancy", value: d.redundancyFactor, weight: (params.W_REDUNDANCY ?? FORGETTING_DEFAULTS.W_REDUNDANCY) },
        { name: "reuse", value: d.reuseFactor, weight: (params.W_REUSE ?? FORGETTING_DEFAULTS.W_REUSE) },
        { name: "drift", value: d.driftFactor, weight: (params.W_DRIFT ?? FORGETTING_DEFAULTS.W_DRIFT) },
        { name: "potential", value: d.potentialFactor, weight: (params.W_POTENTIAL ?? FORGETTING_DEFAULTS.W_POTENTIAL) },
    ];
    const relevance = row.type === "reference"
        ? (params.REFERENCE_RELEVANCE ?? FORGETTING_DEFAULTS.REFERENCE_RELEVANCE)
        : 1.0;
    const contributions = components.map((c) => ({ ...c, contribution: c.value * c.weight * relevance }));
    const dominant = [...contributions].sort((a, b) => b.contribution - a.contribution)[0];
    const threshold = (params.SOFT_FORGET_SCORE ?? FORGETTING_DEFAULTS.SOFT_FORGET_SCORE);
    let verdict;
    if (d.score < threshold) {
        verdict = `below soft-forget threshold (${d.score.toFixed(3)} < ${threshold})`;
    } else if (d.daysSinceLastUse >= (params.SOFT_FORGET_DAYS ?? FORGETTING_DEFAULTS.SOFT_FORGET_DAYS) && d.useCount < 1) {
        verdict = `long-unused (${d.daysSinceLastUse.toFixed(1)}d, zero use) but score ${d.score.toFixed(3)} >= threshold`;
    } else {
        verdict = `retained (score ${d.score.toFixed(3)})`;
    }
    return {
        score: d.score,
        components: contributions,
        dominant: dominant.name,
        verdict,
        diagnostics: d,
    };
}

/**
 * Classify a score into a discrete band relative to the forget thresholds.
 * Useful for threshold-sensitivity analysis and for surfacing borderline rows.
 * @param score - The v2 score.
 * @param params - Overrides.
 * @returns `{ band, pctAboveSoftForget, softForgetScore, archiveScore }`.
 */
export function scoreBand(score, params = {}) {
    const cfg = { ...FORGETTING_DEFAULTS, ...params };
    const soft = cfg.SOFT_FORGET_SCORE;
    const archive = 0.5; // archive is a stricter retention bar (hardcoded reference)
    let band;
    if (score < soft) band = "forget-candidate";
    else if (score < archive) band = "soft-zone";
    else band = "retained";
    return {
        band,
        pctAboveSoftForget: ((score - soft) / Math.max(1e-9, soft)) * 100,
        softForgetScore: soft,
        archiveScore: archive,
    };
}

export function scoreMemory(row, usage, nowIso, ctx = {}, params = {}) {
    const cfg = { ...FORGETTING_DEFAULTS, ...params };
    // Adversarial robustness: a non-finite useCount (NaN/Infinity) must not
    // poison the score. Treat it as zero (unknown usage) rather than NaN.
    const rawUseCount = usage?.useCount ?? 0;
    const useCount = Number.isFinite(rawUseCount) ? Math.max(0, rawUseCount) : 0;
    const lastUsedAt = usage?.lastUsedAt ?? row.updated_at;
    const days = daysSince(lastUsedAt, nowIso);

    // Dimension 1: temporal decay (Ebbinghaus). High when recently used.
    const timeFactor = Math.exp(-cfg.DECAY_RATE * days);
    // Dimension 2: usage frequency (saturating). High when used often.
    // Dimension 2: usage frequency, evidence-weighted shrink toward neutral.
    // Low-evidence memories (few uses) shrink toward 0.5 so "used once" and
    // "used zero" are not over-distinguished; high-evidence memories keep
    // the linear saturating value. EVIDENCE_HALF is the use count at which
    // the shrink is half-way (evidence half-life).
    const linearUsage = Math.min(1, useCount / cfg.USAGE_SATURATION);
    const shrink = useCount / (useCount + cfg.EVIDENCE_HALF);
    const usageFactor = useCount === 0 ? 0 : 0.5 + (linearUsage - 0.5) * shrink;
    // Dimension 3: content redundancy. High when few same-topic siblings;
    // low when the topic is crowded (duplicate content is forgettable).
    const siblings = ctx?.sameTopicCount ?? 0;
    const redundancyFactor = 1 / (1 + siblings / cfg.REDUNDANCY_SATURATION);
    // Dimension 4: cross-project reuse value. High when referenced elsewhere.
    const crossRefs = ctx?.crossWorkspaceRefs ?? 0;
    const reuseFactor = Math.min(1, (crossRefs + (row.scope === "global" ? 1 : 0)) / Math.max(1, cfg.REUSE_BOOST));
    // Dimension 5: topic drift. High when the memory matches an active topic;
    // low (decay toward 0) when it drifts away from current work.
    const activeTopics = ctx?.activeTopics ?? [];
    const topicHits = activeTopics.some((t) => row.title.toLowerCase().includes(t.toLowerCase()) || row.description.toLowerCase().includes(t.toLowerCase()));
    const driftFactor = topicHits ? cfg.TOPIC_MATCH_BONUS : 0.2;

    // Dimension 6: survival potential (v6, SF-AMS Eq.3). A stateful
    // accumulator that carries memory-across-patrols; high when the memory
    // has repeatedly proven useful, low when it has decayed. Optional — a
    // caller without a stored potential (or on first run) gets the neutral
    // value 0.5 so this dimension does not skew the composite.
    const potential = Number.isFinite(ctx?.potential) ? Math.min(1, Math.max(0, ctx.potential)) : 0.5;

    const rawScore = Math.min(1,
        cfg.W_TIME * timeFactor
        + cfg.W_USAGE * usageFactor
        + cfg.W_REDUNDANCY * redundancyFactor
        + cfg.W_REUSE * reuseFactor
        + cfg.W_DRIFT * driftFactor
        + cfg.W_POTENTIAL * potential
    );
    // Reference-type memories are lower-value than user/feedback (they are
    // external pointers, not identity/preferences). Apply a relevance floor
    // so a long-unused reference genuinely drops below the soft-forget
    // threshold instead of being held up by the redundancy/drift floor.
    const score = row.type === "reference"
        ? rawScore * (cfg.REFERENCE_RELEVANCE ?? FORGETTING_DEFAULTS.REFERENCE_RELEVANCE)
        : rawScore;
    return {
        score,
        timeFactor,
        usageFactor,
        redundancyFactor,
        reuseFactor,
        driftFactor,
        potentialFactor: potential,
        daysSinceLastUse: days,
        useCount,
        sameTopicCount: siblings,
        crossWorkspaceRefs: crossRefs,
        topicDrift: !topicHits,
        matchedActiveTopic: topicHits,
    };
}

/**
 * Survival potential dynamics (SF-AMS Eq.3): Φ(t+1) = max(0, Φ(t) + I·Γ_usage·Ψ_div − λ).
 *
 * This is the "make it bigger" upgrade: the composite score I(m) is the
 * instantaneous importance (from `scoreMemory`), and the survival potential
 * Φ is a *stateful* accumulator that carries memory-across-patrols. A memory
 * that is repeatedly important and used keeps rising; one that drifts into
 * irrelevance decays toward the floor. This turns a static scorer into a
 * dynamic evolving memory system — the core conceptual difference between
 * SF-AMS and a plain recompute-each-time heuristic.
 *
 * @param current - The current survival potential Φ(t) (from the stored field,
 *   or 0 for a fresh memory).
 * @param importance - The instantaneous importance I(m) ∈ [0,1] (usually the
 *   `score` from `scoreMemory`).
 * @param used - Whether the memory was accessed this cycle (Γ_usage ∈ {0,1}).
 * @param diversity - The diversity modulation Ψ_div ∈ [0, 1+α_div] (default 1).
 *   Use `diversityModulation` to compute it from semantic redundancy.
 * @param params - Overrides for POTENTIAL_DECAY / POTENTIAL_FLOOR.
 * @returns The new survival potential Φ(t+1), floored at POTENTIAL_FLOOR.
 */
export function updatePotential(current, importance, used, diversity = 1, params = {}) {
    const cfg = { ...FORGETTING_DEFAULTS, ...params };
    // Adversarial robustness: non-finite inputs must not poison the potential.
    const phi = Number.isFinite(current) ? Math.max(cfg.POTENTIAL_FLOOR, current) : cfg.POTENTIAL_FLOOR;
    const imp = Number.isFinite(importance) ? Math.min(1, Math.max(0, importance)) : 0;
    const gamma = used ? 1 : 0;
    const div = Number.isFinite(diversity) ? Math.max(0, diversity) : 1;
    const next = phi + imp * gamma * div - cfg.POTENTIAL_DECAY;
    return Math.max(cfg.POTENTIAL_FLOOR, next);
}

/**
 * Diversity modulation Ψ_div (SF-AMS Eq.4): a smooth gating over semantic
 * redundancy. Highly similar memories are down-weighted (redundant content is
 * less worth reinforcing), while novel memories are amplified.
 *
 *   Ψ_div = 1 + α_div · tanh(β · (τ − Sim(m_i, M_t)))
 *
 * @param similarity - Semantic similarity Sim(m_i, M_t) ∈ [0,1] between the
 *   memory and its most similar sibling. dsh has no embedding layer, so this
 *   is a caller-supplied measure; a caller may fall back to a topic-overlap
 *   count normalized to [0,1], or pass 1 (neutral) when unknown.
 * @param params - Overrides for DIVERSITY_ALPHA / DIVERSITY_TAU / DIVERSITY_BETA.
 * @returns Ψ_div ∈ [0, 1+α_div]. Neutral (1.0) when similarity equals τ.
 */
export function diversityModulation(similarity, params = {}) {
    const cfg = { ...FORGETTING_DEFAULTS, ...params };
    const sim = Number.isFinite(similarity) ? Math.min(1, Math.max(0, similarity)) : 1;
    return 1 + cfg.DIVERSITY_ALPHA * Math.tanh(cfg.DIVERSITY_BETA * (cfg.DIVERSITY_TAU - sim));
}

/**
 * Non-uniform tiered forgetting rate (SF-AMS Table 4).
 *
 * SF-AMS measures actual forget ratios per importance tier: Core 0.00%,
 * Important 14.85%, Secondary 39.83%, Irrelevant 64.74%. The lesson is that
 * forgetting is *non-uniform* — the lowest tier is aggressively pruned while
 * the top tier is essentially never touched. Our `scoreBand` has three bands;
 * this extends it to four tiers and returns the per-tier forget rate, so a
 * caller can scale a memory's eviction priority by which tier it sits in.
 *
 * @param score - The composite score ∈ [0,1].
 * @param params - Overrides for SOFT_FORGET_SCORE.
 * @returns `{ tier, label, forgetRate }` where `tier` is 1-4 (1 = Core,
 *   highest value; 4 = Irrelevant, lowest value) and `forgetRate` is the
 *   SF-AMS-calibrated eviction probability for that tier.
 */
export function tieredForgetRate(score, params = {}) {
    const cfg = { ...FORGETTING_DEFAULTS, ...params };
    const s = Number.isFinite(score) ? Math.min(1, Math.max(0, score)) : 0;
    // Tier boundaries derived from SF-AMS Table 4 (avg importance per tier):
    // Core 0.930 / Important 0.745 / Secondary 0.546 / Irrelevant 0.356.
    if (s >= 0.80) {
        return { tier: 1, label: "core", forgetRate: 0.0 };
    }
    if (s >= 0.60) {
        return { tier: 2, label: "important", forgetRate: 0.1485 };
    }
    if (s >= cfg.SOFT_FORGET_SCORE) {
        return { tier: 3, label: "secondary", forgetRate: 0.3983 };
    }
    return { tier: 4, label: "irrelevant", forgetRate: 0.6474 };
}

/**
 * Whether a memory is protected from forgetting (hard-coded rules).
 * @param row - A memories row.
 * @param correctsOwners - Count of active rows whose `corrects` points at this id.
 * @returns true when the memory must never be forgotten.
 */
export function isProtected(row, correctsOwners = 0) {
    if (row.type === "user" || row.type === "feedback") {
        return true;
    }
    if (row.probation_until) {
        return true;
    }
    if (correctsOwners > 0) {
        return true;
    }
    return false;
}

/**
 * Whether a row is eligible for the first-stage soft forget.
 * @param row - A memories row (must be active).
 * @param usage - `{ useCount, lastUsedAt } | undefined`.
 * @param correctsOwners - Count of active rows whose `corrects` points at this id.
 * @param nowIso - Reference instant.
 * @param ctx - Context for extra dimensions (see scoreMemory).
 * @param params - Overrides.
 * @returns `{ eligible, reason, diagnostics }`.
 */
export function softForgetEligible(row, usage, correctsOwners, nowIso, ctx = {}, params = {}) {
    const cfg = { ...FORGETTING_DEFAULTS, ...params };
    if (row.status !== "active") {
        return { eligible: false, reason: "not-active" };
    }
    if (row.soft_forgotten_at) {
        // v3 re-evaluation: a soft-forgotten row may deserve restoration if its
        // v2 multi-dimensional score has risen back above the threshold (e.g.
        // it was soft-forgotten by an earlier single-dimension pass, or it was
        // re-used since). This is the recovery path that keeps "soft forget"
        // from becoming a one-way door.
        const diag = scoreMemory(row, usage, nowIso, ctx, params);
        if (diag.score >= cfg.SOFT_FORGET_SCORE) {
            return { eligible: false, reason: "restore", shouldRestore: true, diagnostics: diag };
        }
        return { eligible: false, reason: "already-soft-forgotten", diagnostics: diag };
    }
    if (isProtected(row, correctsOwners)) {
        return { eligible: false, reason: "protected" };
    }
    const diagnostics = scoreMemory(row, usage, nowIso, ctx, params);
    const topicMatched = diagnostics.topicDrift === false;
    // A memory matching an active topic is part of the current work context.
    // Even if it has not been read directly, it is background knowledge the
    // active project depends on — the long-unused path must not drop it on
    // age alone; it also has to score below the threshold.
    if (diagnostics.daysSinceLastUse >= cfg.SOFT_FORGET_DAYS && diagnostics.useCount < 1 && !topicMatched) {
        return { eligible: true, reason: "long-unused-zero-use", diagnostics };
    }
    if (diagnostics.score < cfg.SOFT_FORGET_SCORE) {
        return { eligible: true, reason: "low-score", diagnostics };
    }
    return { eligible: false, reason: "above-threshold", diagnostics };
}

/**
 * Whether a soft-forgotten row is eligible for the second-stage archive.
 * @param row - A memories row (active + soft_forgotten_at set).
 * @param nowIso - Reference instant.
 * @param params - Overrides.
 * @returns `{ eligible, reason, daysSinceForget }`.
 */
export function archiveEligible(row, nowIso, params = {}) {
    const cfg = { ...FORGETTING_DEFAULTS, ...params };
    if (!row.soft_forgotten_at) {
        return { eligible: false, reason: "not-soft-forgotten" };
    }
    const days = daysSince(row.soft_forgotten_at, nowIso);
    if (days >= cfg.ARCHIVE_DAYS) {
        return { eligible: true, reason: "forgotten-long-enough", daysSinceForget: days };
    }
    return { eligible: false, reason: "still-recent", daysSinceForget: days };
}

/**
 * Whether an archived memory should be un-archived (brought back to active).
 * An archived row is history — it was forgotten for a long time and moved out
 * of the injection list. It returns only when it has earned its way back:
 *   1. Its v2 score rose above UNARCHIVE_SCORE (re-retrieved / re-used), or
 *   2. It was explicitly re-used since archiving (use_count > 0).
 * The score is computed the same way as an active row so the two paths agree.
 * @param row - An archived memories row (status = 'archived').
 * @param usage - `{ useCount, lastUsedAt }` or null.
 * @param nowIso - Reference instant.
 * @param params - Overrides.
 * @returns `{ eligible, reason, score }`.
 */
export function unarchiveEligible(row, usage, nowIso, params = {}) {
    const cfg = { ...FORGETTING_DEFAULTS, ...params };
    if (row.status !== "archived") {
        return { eligible: false, reason: "not-archived", score: null };
    }
    // A row merged into a newer version (merged_into set) is a superseded
    // duplicate: it must never come back — the replacement is the canonical
    // copy, and restoring the old one would create two active rows for the
    // same fact. Only genuinely-dead archived rows (no merge target) are
    // eligible for re-evaluation.
    if (row.merged_into) {
        return { eligible: false, reason: "merged-superseded", score: null };
    }
    // Re-used since archiving: always worth restoring.
    const rawUseCount = usage?.useCount ?? 0;
    const useCount = Number.isFinite(rawUseCount) ? Math.max(0, rawUseCount) : 0;
    if (useCount > 0) {
        return { eligible: true, reason: "reused-since-archive", score: null };
    }
    // Score re-evaluation: compute fresh and compare against the threshold.
    const d = scoreMemory(row, usage, nowIso, {}, params);
    if (d.score >= cfg.UNARCHIVE_SCORE) {
        return { eligible: true, reason: "score-recovered", score: d.score };
    }
    return { eligible: false, reason: "score-low", score: d.score };
}

/**
 * Scan archived rows of one partition and propose un-archiving those that have
 * earned their way back. Pure — the caller decides whether to apply.
 * @param repo - The memories repository (needs listArchivedRows + getUsage).
 * @param workspaceId - The partition.
 * @param nowIso - Reference instant.
 * @param params - Overrides.
 * @returns `{ unarchiveCandidates, scanned }`.
 */
export function scanUnarchive(repo, workspaceId, nowIso, params = {}) {
    const rows = repo.listArchivedRows ? repo.listArchivedRows(workspaceId, 500) : [];
    const unarchiveCandidates = [];
    const scanned = [];
    for (const row of rows) {
        const usage = repo.getUsage ? repo.getUsage(workspaceId, [row.id]) : null;
        const u = usage ? { useCount: usage.use_count, lastUsedAt: usage.last_used_at } : null;
        const verdict = unarchiveEligible(row, u, nowIso, params);
        scanned.push({
            id: row.id,
            title: row.title,
            type: row.type,
            useCount: u?.useCount ?? 0,
            eligible: verdict.eligible,
            reason: verdict.reason,
            score: verdict.score,
        });
        if (verdict.eligible) {
            unarchiveCandidates.push({ id: row.id, title: row.title, reason: verdict.reason, score: verdict.score });
        }
    }
    return { unarchiveCandidates, scanned };
}

/**
 * Extract keyword tokens from a memory's title + description for topic
 * clustering. Words >= 4 chars, lowercased, deduped. A memory belongs to a
 * topic cluster when it shares >= 2 keywords with a sibling.
 *
 * Description-only tokens are NOT used to derive a topic: descriptions often
 * carry generic placeholders ("desc", "body", "a memory about...") that would
 * create false topic matches across unrelated memories. The title is the
 * authoritative topic signal; description tokens only supplement an
 * already-title-derived keyword (never introduce a new one alone).
 * @param row - A memories row.
 * @returns Unique lowercase keyword tokens.
 */
function topicTokens(row) {
    const titleTokens = (row.title ?? "").toLowerCase().match(/[a-z0-9]{4,}/g) ?? [];
    const descTokens = (row.description ?? "").toLowerCase().match(/[a-z0-9]{4,}/g) ?? [];
    const tokens = new Set(titleTokens);
    // Supplement: description tokens only add words already present in the title.
    for (const d of descTokens) {
        if (titleTokens.includes(d)) {
            tokens.add(d);
        }
    }
    return [...tokens];
}

/**
 * Build the per-row context needed for v2 scoring:
 *   - sameTopicCount: active siblings sharing >= 2 topic keywords.
 *   - crossWorkspaceRefs: references from other workspaces (usage-accounted).
 * @param rows - All active rows in the partition.
 * @param repo - The memories repository (for cross-workspace queries).
 * @param workspaceId - The partition.
 * @param activeTopics - Active project topic keywords (optional).
 * @returns Map of id -> context.
 */
function buildRowContext(rows, repo, workspaceId, activeTopics = []) {
    const tokenSets = new Map();
    for (const row of rows) {
        tokenSets.set(row.id, topicTokens(row));
    }
    const sameTopicCount = new Map();
    for (const row of rows) {
        const a = tokenSets.get(row.id);
        let count = 0;
        for (const other of rows) {
            if (other.id === row.id) {
                continue;
            }
            const b = tokenSets.get(other.id);
            const shared = a.filter((t) => b.includes(t));
            if (shared.length >= 2) {
                count += 1;
            }
        }
        sameTopicCount.set(row.id, count);
    }
    // Cross-workspace refs: count usage records in OTHER workspaces.
    const crossWorkspaceRefs = new Map();
    for (const row of rows) {
        crossWorkspaceRefs.set(row.id, 0);
    }
    // Best-effort: list other workspaces and sum their usage for this id.
    try {
        for (const w of repo.workspaceList()) {
            if (w.workspace_id === workspaceId) {
                continue;
            }
            for (const row of rows) {
                const u = repo.getUsage(w.workspace_id, [row.id]);
                if (u && u.use_count > 0) {
                    crossWorkspaceRefs.set(row.id, (crossWorkspaceRefs.get(row.id) ?? 0) + u.use_count);
                }
            }
        }
    }
    catch {
        // Cross-workspace is best-effort; never fail the scan.
    }
    return { sameTopicCount, crossWorkspaceRefs };
}

/**
 * Scan one partition's active rows and return two candidate lists:
 * soft-forget candidates and archive candidates. Pure — it does not mutate
 * the store; the caller decides whether to apply.
 *
 * @param repo - The memories repository (needs listRows + getUsage + workspaceList).
 * @param workspaceId - The partition to scan.
 * @param nowIso - Reference instant for deterministic tests.
 * @param params - Overrides.
 * @returns `{ softForgetCandidates, archiveCandidates, scanned }`.
 */
export function scanForgetting(repo, workspaceId, nowIso, params = {}) {
    const cfg = { ...FORGETTING_DEFAULTS, ...params };
    const rows = repo.listRows(workspaceId); // active, injection order
    const usageRows = new Map();
    for (const row of rows) {
        const usage = repo.getUsage(workspaceId, [row.id]);
        if (usage) {
            usageRows.set(row.id, { useCount: usage.use_count, lastUsedAt: usage.last_used_at });
        }
    }
    // Count how many active rows point `corrects` at each id.
    const correctsOwners = new Map();
    for (const row of rows) {
        if (row.corrects) {
            const target = typeof row.corrects === "string" ? row.corrects : String(row.corrects);
            correctsOwners.set(target, (correctsOwners.get(target) ?? 0) + 1);
        }
    }
    // v2 context: topic clusters + cross-workspace reuse.
    const activeTopics = params.activeTopics ?? [];
    const { sameTopicCount, crossWorkspaceRefs } = buildRowContext(rows, repo, workspaceId, activeTopics);

    const softForgetCandidates = [];
    const archiveCandidates = [];
    const restoreCandidates = [];
    const scanned = [];
    let activeCount = rows.length;

    for (const row of rows) {
        const usage = usageRows.get(row.id);
        const owners = correctsOwners.get(row.id) ?? 0;
        const ctx = {
            sameTopicCount: sameTopicCount.get(row.id) ?? 0,
            crossWorkspaceRefs: crossWorkspaceRefs.get(row.id) ?? 0,
            activeTopics,
        };
        const eligible = softForgetEligible(row, usage, owners, nowIso, ctx, params);
        scanned.push({
            id: row.id,
            title: row.title,
            type: row.type,
            useCount: usage?.useCount ?? 0,
            lastUsedAt: usage?.lastUsedAt ?? row.updated_at,
            protected: eligible.reason === "protected",
            score: eligible.diagnostics?.score ?? null,
            softForgotten: Boolean(row.soft_forgotten_at),
            sameTopicCount: ctx.sameTopicCount,
            crossWorkspaceRefs: ctx.crossWorkspaceRefs,
        });

        if (row.soft_forgotten_at) {
            // v3 re-evaluation: if the v2 score rose above threshold, propose restore.
            if (eligible.shouldRestore) {
                restoreCandidates.push({ id: row.id, title: row.title, reason: "score-recovered", score: eligible.diagnostics?.score ?? null });
                continue;
            }
            // Second stage: already demoted, check archive eligibility.
            const arch = archiveEligible(row, nowIso, params);
            if (arch.eligible && activeCount > cfg.MIN_ACTIVE) {
                archiveCandidates.push({ id: row.id, title: row.title, reason: arch.reason, daysSinceForget: arch.daysSinceForget });
            }
            continue;
        }

        if (eligible.eligible && activeCount > cfg.MIN_ACTIVE) {
            softForgetCandidates.push({ id: row.id, title: row.title, reason: eligible.reason, score: eligible.diagnostics?.score ?? null, daysSinceLastUse: eligible.diagnostics?.daysSinceLastUse ?? null });
        }
    }

    return { softForgetCandidates, archiveCandidates, restoreCandidates, scanned };
}

/**
 * Association & propagation analysis: would forgetting `targetId` break a
 * chain? A memory is "load-bearing" when:
 *   1. It corrects / is corrected by other memories (corrects chain),
 *   2. It is the sole sibling in a topic cluster (its content is unique),
 *   3. It is cross-workspace referenced (removing it would orphan others).
 *
 * @param repo - The memories repository.
 * @param workspaceId - The partition.
 * @param targetId - The candidate to test.
 * @returns `{ loadBearing, reasons, chainCount, uniqueSibling, crossRefs }`.
 */
export function propagationRisk(repo, workspaceId, targetId, nowIso) {
    const rows = repo.listRows(workspaceId);
    const target = rows.find((r) => r.id === targetId);
    if (!target) {
        return { loadBearing: false, reasons: ["not-found"], chainCount: 0, uniqueSibling: false, crossRefs: 0 };
    }
    const reasons = [];
    // 1. corrects chain: who does this correct, and who corrects this?
    let chainCount = 0;
    if (target.corrects) {
        chainCount += 1;
        reasons.push("corrects-another");
    }
    const correctedBy = rows.filter((r) => r.corrects === targetId);
    if (correctedBy.length > 0) {
        chainCount += correctedBy.length;
        reasons.push("corrected-by-others");
    }
    // 2. topic cluster uniqueness: is this the only memory on its topic?
    const targetTokens = topicTokens(target);
    const siblings = rows.filter((r) => r.id !== targetId && topicTokens(r).filter((t) => targetTokens.includes(t)).length >= 2);
    const uniqueSibling = siblings.length === 0;
    if (uniqueSibling) {
        reasons.push("sole-topic-holder");
    }
    // 3. cross-workspace refs.
    let crossRefs = 0;
    try {
        for (const w of repo.workspaceList()) {
            if (w.workspace_id === workspaceId) {
                continue;
            }
            const u = repo.getUsage(w.workspace_id, [targetId]);
            if (u && u.use_count > 0) {
                crossRefs += u.use_count;
            }
        }
    }
    catch {
        // best-effort
    }
    if (crossRefs > 0) {
        reasons.push("cross-workspace-referenced");
    }
    const loadBearing = chainCount > 0 || uniqueSibling || crossRefs > 0;
    return { loadBearing, reasons, chainCount, uniqueSibling, crossRefs };
}

/**
 * Overflow backfill (criterion 4): when the injection budget cannot fit the
 * current active set, rank every non-protected active row by forget score and
 * propose soft-forgetting the lowest-scoring ones until the projected index
 * fits, OR until a minimum active count is reached. Pure — returns a ranked
 * proposal list; the caller applies via `softForgetRow`.
 *
 * The projection cost is a coarse stand-in for the real `fitTiered` estimate:
 * we price a hook line at `PROJECTED_LINE_TOKENS` and compare the projected
 * total against `maxTokens`. This is a backfill trigger, not the precise fit
 * (which stays in `token-budget.js`); it answers "would the budget overflow?"
 * with a safety margin so the render path does not have to degrade.
 *
 * @param repo - The memories repository.
 * @param workspaceId - The partition.
 * @param maxTokens - The injection token budget.
 * @param nowIso - Reference instant.
 * @param params - Overrides.
 * @returns `{ wouldOverflow, projectedTokens, proposals }`.
 */
export function overflowBackfill(repo, workspaceId, maxTokens, nowIso, params = {}) {
    const cfg = { ...FORGETTING_DEFAULTS, ...params };
    const rows = repo.listInjectedRows(workspaceId);
    if (rows.length === 0) {
        return { wouldOverflow: false, projectedTokens: 0, proposals: [] };
    }
    const perLine = cfg.PROJECTED_LINE_TOKENS;
    let projected = rows.length * perLine;
    const wouldOverflow = projected > maxTokens;
    if (!wouldOverflow) {
        return { wouldOverflow, projectedTokens: projected, proposals: [] };
    }
    // Rank by forget score ascending (lowest = first to go), skipping protected
    // and already-soft-forgotten (they are not in the injection list anyway).
    const usageRows = new Map();
    for (const row of rows) {
        const usage = repo.getUsage(workspaceId, [row.id]);
        if (usage) {
            usageRows.set(row.id, { useCount: usage.use_count, lastUsedAt: usage.last_used_at });
        }
    }
    const correctsOwners = new Map();
    for (const row of rows) {
        if (row.corrects) {
            const target = typeof row.corrects === "string" ? row.corrects : String(row.corrects);
            correctsOwners.set(target, (correctsOwners.get(target) ?? 0) + 1);
        }
    }
    const activeTopics = params.activeTopics ?? [];
    const { sameTopicCount, crossWorkspaceRefs } = buildRowContext(rows, repo, workspaceId, activeTopics);
    const ranked = rows
        .map((row) => {
            const usage = usageRows.get(row.id);
            const owners = correctsOwners.get(row.id) ?? 0;
            const ctx = {
                sameTopicCount: sameTopicCount.get(row.id) ?? 0,
                crossWorkspaceRefs: crossWorkspaceRefs.get(row.id) ?? 0,
                activeTopics,
            };
            const eligible = softForgetEligible(row, usage, owners, nowIso, ctx, params);
            return {
                row,
                score: eligible.diagnostics?.score ?? 0,
                protected: eligible.reason === "protected",
                eligible: eligible.eligible,
            };
        })
        .sort((a, b) => a.score - b.score);
    const proposals = [];
    let remaining = rows.length;
    const budgetPressure = projected > maxTokens * (cfg.OVERFLOW_EVICTION_FRACTION ?? 1.15);
    for (const item of ranked) {
        if (remaining <= cfg.MIN_ACTIVE) {
            break;
        }
        if (item.protected) {
            continue;
        }
        // Normal eligibility path: only demote a memory that is actually
        // forgettable by the soft-forget criteria. Under genuine budget
        // pressure (projection exceeds budget by the eviction fraction),
        // allow demoting the lowest-scoring rows even when they sit above
        // the threshold — the alternative is an unbounded injection.
        if (!item.eligible && !budgetPressure) {
            continue;
        }
        proposals.push({
            id: item.row.id,
            title: item.row.title,
            score: item.score,
            projectedAfter: projected - perLine,
        });
        projected -= perLine;
        remaining -= 1;
        if (projected <= maxTokens) {
            break;
        }
    }
    return { wouldOverflow, projectedTokens: projected, proposals };
}
