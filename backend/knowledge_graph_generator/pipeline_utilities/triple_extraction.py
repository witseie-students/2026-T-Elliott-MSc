from __future__ import annotations
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Set, Tuple, Any
import time

from pydantic import BaseModel
from openai import OpenAI
from collections import defaultdict
import time
from typing import Dict, List, Tuple, Any, Set

from collections import defaultdict
from typing import Dict, List, Set, Tuple, Any
import time

from django.conf import settings

# Set up the OpenAI client with your API key
client = OpenAI(api_key=settings.OPENAI_API_KEY)

def _tstamp(msg: str, start: float | None = None) -> float:
    """Print a timing line and return current perf_counter."""
    now = time.perf_counter()
    if start is not None:
        print(f"⏱ {msg}: {(now - start):.3f}s")
    else:
        print(f"⏱ {msg}")
    return now

# -----------------------------------------
# Pydantic Models for API Responses
# -----------------------------------------

class Entity(BaseModel):
    name: str
    types: list[str]  # Entity types

class QuadrupleWithEntityTypes(BaseModel):
    subject: Entity
    predicate: str
    predicate_types: list[str]  # NEW: Predicate types
    object: Entity
    reason: str

class KnowledgeQuadruplesWithEntitiesResponse(BaseModel):
    quadruples: list[QuadrupleWithEntityTypes]

# { "clusters": [ { "cluster_id": ..., "connects_to": [...], "quadruples": [...] }, ... ] }

class ClusterBlock(BaseModel):
    cluster_id: int
    connects_to: List[int] = []                # optional; model may omit
    quadruples: List[QuadrupleWithEntityTypes]


class ClusteredInferenceResponse(BaseModel):
    clusters: List[ClusterBlock]


# -----------------------------------------
# FUNCTION TO EXTRACT QUADRUPLES
# -----------------------------------------

def extract_quadruples_with_entity_types(sentence):
    """
    Extracts knowledge quadruples (with entity and predicate types) from a given sentence using the OpenAI API.
    :param sentence: The input sentence.
    :return: List of quadruples with entity and predicate types.
    """
    try:
        completion = client.beta.chat.completions.parse(
            model="gpt-4.1-nano",
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Extract knowledge quadruples and their types for every relationship in the given sentence. "
                        "Each quadruple should include:\n"
                        "1. **Subject**: Provide the subject name and a list of possible ontological types for the entity.\n"
                        "2. **Predicate**: Provide the predicate and a list of possible ontological types for the predicate.\n"
                        "3. **Object**: Provide the object name and a list of possible ontological types for the entity.\n"
                        "4. **Reason**: Provide reasoning for the extraction of the relationship with context from the rest of the sentence so that the triple completely represents the sentence.\n\n"
                        "Do not leave any possible quadruples out. Represent the information in the sentence as accurately as possible. All quadruples must be able to fully represent the original sentence through their reason. "
                        "Ensure the response is in JSON format."
                    ),
                },
                {"role": "user", "content": sentence},
            ],
            response_format=KnowledgeQuadruplesWithEntitiesResponse,
        )
        quadruples = completion.choices[0].message.parsed.quadruples
        return [quadruple.dict() for quadruple in quadruples]
    except Exception as e:
        raise RuntimeError(f"Failed to extract quadruples with entity types: {e}")


# -----------------------------------------
# FUNCTION TO CONVERT QUADRUPLE TO SENTENCE
# -----------------------------------------

def quadruple_to_sentence(quadruple, model="gpt-4o-mini-2024-07-18"):
    """
    Converts a knowledge quadruple into a natural-sounding sentence.

    The quadruple dictionary should have the following structure:
    
        {
            "subject": {
                "name": <subject_name>,
                "types": [<subject_type1>, <subject_type2>, ...]
            },
            "predicate": <predicate>,
            "predicate_types": [<predicate_type1>, ...],  # Optional
            "object": {
                "name": <object_name>,
                "types": [<object_type1>, <object_type2>, ...]
            },
            "reason": <reason for the relationship>
        }
    
    This function constructs a structured prompt to clearly present each element to the LLM.

    :param quadruple: Dictionary representing a quadruple with entity and predicate types.
    :param model: The ChatGPT model to use.
    :return: A natural language sentence.
    """
    # Extract components from the quadruple.
    subject_name = quadruple["subject"]["name"]
    subject_types = ", ".join(quadruple["subject"]["types"])
    predicate = quadruple["predicate"]
    predicate_types = ", ".join(quadruple.get("predicate_types", []))
    object_name = quadruple["object"]["name"]
    object_types = ", ".join(quadruple["object"]["types"])
    reason = quadruple["reason"]

    # Create a structured input for the LLM.
    structured_input = (
        "Please convert the following structured knowledge quadruple into a natural-sounding sentence:\n\n"
        f"Subject: {subject_name}\n"
        #f"Subject Types: {subject_types}\n\n"
        f"Predicate: {predicate}\n"
        #f"Predicate Types: {predicate_types if predicate_types else 'None'}\n\n"
        f"Object: {object_name}\n"
        #f"Object Types: {object_types}\n\n"
        f"Reason: {reason}\n\n"
        "Natural language sentence:"
    )

    system_prompt = (
        "You are an expert language assistant. Your task is to transform structured knowledge graph triples into a coherent, natural-sounding sentence."
    )

    try:
        completion = client.beta.chat.completions.parse(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": structured_input},
            ]
        )
        # Strip leading/trailing whitespace.
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"An error occurred while converting quadruple to sentence: {e}")
        return None



# ===============================================================
#  CLUSTERING & INFERENCE  (2025-07-31c – canonical names + diagnostics)
# ===============================================================

import re, time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Tuple, Any, Set

# ---------- Type aliases ----------
Quadruple    = Dict[str, Any]
ClustersDict = Dict[str, List[Quadruple]]          # root → quads

# ---------- Helpers ----------
def _tstamp(msg: str, tic: float | None = None) -> float:
    now = time.perf_counter()
    print(f"⏱ {msg}" + (f": {(now-tic):.3f}s" if tic else ""))
    return now

_canon_rgx = re.compile(r"\s+")
def _canon(s: str) -> str:
    """Cheap canonicaliser: lower-case, trim, collapse whitespace."""
    return _canon_rgx.sub(" ", str(s).strip().lower())

# ===============================================================
#  CLUSTERING  (Union-Find on canonical entity names)
# ===============================================================

def _cluster(quads: List[Quadruple]) -> ClustersDict:
    tic = time.perf_counter()
    parent: Dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for q in quads:
        sa, ob = _canon(q["subject"]["name"]), _canon(q["object"]["name"])
        union(sa, ob)

    clusters: ClustersDict = defaultdict(list)
    for q in quads:
        clusters[ find(_canon(q["subject"]["name"])) ].append(q)

    _tstamp(f"cluster() | {len(quads)} quads ➜ {len(clusters)} clusters", tic)
    return clusters


def _quad_key(q: Quadruple) -> Tuple[str, str, str]:
    """Canonical key → duplicates collapse even with minor text variation."""
    return (
        _canon(q["subject"]["name"]),
        _canon(q["predicate"]),
        _canon(q["object"]["name"]),
    )

# ===============================================================
#  PROMPT CONSTANTS
# ===============================================================

_JSON_SCHEMA = (
    "Return **JSON only** like:\n"
    '{ "quadruples": [ { '
    '"subject":{"name":"...","types":["..."]}, '
    '"predicate":"...", "predicate_types":["..."], '
    '"object":{"name":"...","types":["..."]}, '
    '"reason":"..." } , … ] }'
)

def _fmt_two(cl_a: List[Quadruple], cl_b: List[Quadruple]) -> str:
    """
    Pretty-printer for two cluster blocks – useful in diagnostics.
    Shows Subject — Predicate → Object lines for each quad.
    """
    f = lambda qs: "\n".join(
        f"• {q['subject']['name']} — {q['predicate']} → {q['object']['name']}"
        for q in qs
    ) or "• (empty)"
    return f"Cluster A:\n{f(cl_a)}\n\nCluster B:\n{f(cl_b)}"


# ===============================================================
#  PHASE-1  (single LLM over *all* clusters)
# ===============================================================

def _phase1(paragraph: str, quads: List[Quadruple]) -> List[Quadruple]:
    """
    Global 'mop-up' pass.

    What it does
    ------------
    • Re-clusters current quads and shows ALL clusters to the LLM in one shot.
    • Asks the model to propose ONLY cross-cluster edges (no within-cluster edges).
    • Prompts "no new entities, no duplicates" – we ALSO enforce this later in code.

    Why it helps
    ------------
    • Sometimes a single global view makes the obvious bridges apparent
      (e.g., when two clusters share a latent relation that only appears in text).

    Returns
    -------
    A list of candidate quadruples (may include non-bridging or unseen-entity edges,
    which the orchestrator filters).
    """
    tic = _tstamp("PH-1 START")
    clusters_text = "\n\n".join(
        f"Cluster {i+1}:\n" + "\n".join(
            f"{q['subject']['name']} — {q['predicate']} → {q['object']['name']}"
            for q in block
        )
        for i, block in enumerate(_cluster(quads).values())
    )

    sys = ("**TASK**: add edges that connect *different* clusters. "
           "No new entities, no duplicates.\n" + _JSON_SCHEMA)
    user = (f"Paragraph:\n{paragraph}\n\nExisting clusters:\n{clusters_text}")

    rsp = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[{"role":"system","content":sys},
                  {"role":"user","content":user}],
        response_format=KnowledgeQuadruplesWithEntitiesResponse,
    )
    out = [q.dict() for q in rsp.choices[0].message.parsed.quadruples]
    _tstamp(f"PH-1 DONE – {len(out)} quads", tic)
    return out


# ===============================================================
#  PHASE-2  (hub-and-spoke pairwise, with success flag)
# ===============================================================

# ===============================================================
#  PHASE-2 helper – _infer_pair  (context-rich + retry logic)
# ===============================================================

def _infer_pair(
    paragraph: str,
    cl_a: List[Quadruple],
    cl_b: List[Quadruple],
    tag: str,
    max_attempts: int = 3,
    n_candidates: int = 3,
) -> List[Quadruple]:
    """
    Try to create at least ONE edge that links Cluster A ↔ Cluster B.

    Improvements vs. previous version
    ---------------------------------
    1. Provide **full triple context** for both clusters (helps reasoning).
    2. Request *n_candidates* edges in a single call – better chance to hit
       a true bridge.
    3. Retry up to *max_attempts* times if no bridge is found.
    """
    namesA = {q["subject"]["name"] for q in cl_a} | {q["object"]["name"] for q in cl_a}
    namesB = {q["subject"]["name"] for q in cl_b} | {q["object"]["name"] for q in cl_b}

    triplesA = "\n".join(f"- {q['subject']['name']} — {q['predicate']} → {q['object']['name']}"
                         for q in cl_a) or "- (empty)"
    triplesB = "\n".join(f"- {q['subject']['name']} — {q['predicate']} → {q['object']['name']}"
                         for q in cl_b) or "- (empty)"

    base_system = (
        f"PAIR {tag} | **GOAL** Create *{n_candidates}* candidate quadruples, "
        "each linking an entity from *Cluster A* to an entity from *Cluster B*.\n"
        "• **Allowed subject/object names** MUST be copied *exactly* from the lists below.\n"
        "• No edges purely within the same cluster.\n"
        "• Provide a short, sensible reason for each.\n\n"
        f"Allowed Cluster A names:\n" + "\n".join(f"- {n}" for n in sorted(namesA)) + "\n\n"
        f"Allowed Cluster B names:\n" + "\n".join(f"- {n}" for n in sorted(namesB)) + "\n\n"
        + _JSON_SCHEMA
    )

    base_user = (
        f"Paragraph for context:\n{paragraph}\n\n"
        "✦ Cluster A triples:\n" + triplesA + "\n\n"
        "✦ Cluster B triples:\n" + triplesB + "\n\n"
        "Return only the JSON object."
    )

    for attempt in range(1, max_attempts + 1):
        rsp = client.beta.chat.completions.parse(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": base_system},
                {"role": "user",   "content": base_user},
            ],
            response_format=KnowledgeQuadruplesWithEntitiesResponse,
        )
        quads = [q.dict() for q in rsp.choices[0].message.parsed.quadruples]

        bridged = any(
            (_canon(q["subject"]["name"]) in map(_canon, namesA) and
             _canon(q["object"]["name"])  in map(_canon, namesB)) or
            (_canon(q["object"]["name"])  in map(_canon, namesA) and
             _canon(q["subject"]["name"]) in map(_canon, namesB))
            for q in quads
        )
        status = "✅ bridged" if bridged else "🚫 no-bridge"
        print(f"   ↳ pair {tag:10} try {attempt}/{max_attempts} → "
              f"{len(quads):2} quads | {status}")

        if bridged or attempt == max_attempts:
            # either we succeeded, or we give up after max_attempts
            return quads

    # unreachable, but keeps type-checkers happy
    return []


def _phase2(paragraph: str, clusters: ClustersDict, max_workers: int) -> List[Quadruple]:
    """
    Hub-and-spoke round: connect the largest cluster (hub) to each other cluster (spoke).

    Why hub-and-spoke?
    -------------------
    • If you always try to bridge via the largest component, you reduce the number of
      clusters quickly (greedy reduction in components).

    Concurrency
    -----------
    • Each (hub ↔ spoke) pair is processed in parallel via a thread pool.

    Returns
    -------
    A flat list of candidate quadruples from all pairwise calls.
    """
    roots = sorted(clusters.items(), key=lambda kv: len(kv[1]), reverse=True)
    if len(roots) <= 1:
        print("PH-2 skipped (graph already connected)")
        return []

    hub_root, hub = roots[0]
    spokes = [(hub, roots[i][1], f"{hub_root[:6]}↔{i+1}") for i in range(1, len(roots))]
    print(f"PH-2 hub-and-spoke: {len(spokes)} pairs")

    outs: List[Quadruple] = []
    with ThreadPoolExecutor(max_workers=max_workers or 1) as pool:
        futs = {pool.submit(_infer_pair, paragraph, a, b, tag): tag for a, b, tag in spokes}
        for f in as_completed(futs):
            try:
                outs.extend(f.result())
            except Exception as e:
                print(f"⚠️ pair {futs[f]} failed: {e}")
    return outs


# ===============================================================
#  PHASE-3  (iterative loop until connected or stalled)
# ===============================================================

def _all_entity_names(quads: List[Quadruple]) -> Set[str]:
    """Collect the canonicalised set of all subject/object names currently in the graph."""
    return {_canon(q["subject"]["name"]) for q in quads} | {_canon(q["object"]["name"]) for q in quads}

def _filter_to_known_entities(cands: List[Quadruple], allowed: Set[str]) -> List[Quadruple]:
    """
    Enforce 'no new entities' at code level (not only in prompts).
    Drops any candidate with a subject/object not present in `allowed`.
    """
    out: List[Quadruple] = []
    for q in cands:
        s = _canon(q["subject"]["name"]); o = _canon(q["object"]["name"])
        if s in allowed and o in allowed:
            out.append(q)
    return out

def _phase3_iterate_until_connected(
    paragraph: str,
    all_q: List[Quadruple],
    seen_keys: Set[Tuple[str, str, str]],
    max_workers: int = 8,
    max_rounds: int = 10,
    patience: int = 2,
    run_global_pass_each_round: bool = False,
) -> Tuple[List[Quadruple], int]:
    """
    Keep attempting targeted pairwise bridges (and optionally a global pass) until:
      1) there's a single connected component, or
      2) cluster count stops improving for `patience` rounds, or
      3) we hit `max_rounds`.

    Parameters
    ----------
    paragraph : str
        The original paragraph (context for the LLM).
    all_q : List[Quadruple]
        The live list of all accepted quads (mutated in-place).
    seen_keys : Set[Tuple[str, str, str]]
        Set of canonical (subject,predicate,object) to deduplicate new quads.
    max_workers : int
        Thread pool size for pairwise calls.
    max_rounds : int
        Hard cap on the number of iterative rounds.
    patience : int
        Early-stop after this many rounds without reducing cluster count.
    run_global_pass_each_round : bool
        If True, run Phase-1 each round as well (safer but slower).

    Returns
    -------
    (added_quads, rounds_run)
    """
    added: List[Quadruple] = []
    rounds = 0
    no_improve = 0

    def _add_many(cands: List[Quadruple]) -> int:
        n = 0
        for q in cands:
            k = _quad_key(q)
            if k not in seen_keys:
                seen_keys.add(k); all_q.append(q); added.append(q); n += 1
        return n

    while rounds < max_rounds:
        rounds += 1
        clusters = _cluster(all_q)
        k0 = len(clusters)
        if k0 <= 1:
            print(f"🔁 LOOP-{rounds}: already connected; stopping")
            break

        print(f"🔁 LOOP-{rounds} START → {k0} clusters")
        before_len = len(all_q)
        allowed = _all_entity_names(all_q)

        # 1) Hub-and-spoke pairwise bridging across current clusters
        n2 = _add_many(_phase2(paragraph, clusters, max_workers))

        # 2) Optional global pass to catch tricky bridges
        n1 = 0
        if run_global_pass_each_round:
            phase1_raw = _phase1(paragraph, all_q)
            phase1 = _filter_to_known_entities(phase1_raw, allowed)
            n1 = _add_many(phase1)

        clusters_after = _cluster(all_q)
        k1 = len(clusters_after)
        print(f"🔁 LOOP-{rounds} DONE: +{(len(all_q)-before_len)} quads | {k1} clusters")

        # Progress / early stopping
        if k1 < k0:
            no_improve = 0
        elif (n1 + n2) == 0:
            no_improve += 1
        else:
            # Quads added but did not reduce components (non-bridging additions)
            no_improve += 1

        if k1 <= 1:
            print("✅ CONNECTED in iterative phase")
            break
        if no_improve >= patience:
            print(f"⚠️ Stalled for {no_improve} round(s); stopping early")
            break

    return added, rounds


# ===============================================================
#  ORCHESTRATOR  (two phases + iterative Phase-3)
# ===============================================================

def two_phase_infer_new_quadruples(
    paragraph: str,
    initial_quads: List[Quadruple],
    max_workers: int = 8,
    # New, optional knobs for the iterative tail:
    max_rounds: int = 10,
    patience: int = 2,
    run_global_pass_each_round: bool = False,
) -> List[Quadruple]:
    """
    High-level controller for 'add bridging edges' workflow.

    Pipeline
    --------
    0) Baseline: cluster and log diagnostics.
    1) Phase-1 (global): single LLM call over all clusters ⇒ candidate bridges.
       – Prompt requests 'no new entities'; we ALSO filter to known entities.
    2) Phase-2 (pairwise): hub-and-spoke over current clusters in parallel.
       – Stronger name constraints; often reduces components fastest.
    3) Phase-3 (iterative): re-cluster, then keep running (2) (and optionally (1))
       until connected, stalled, or `max_rounds` reached.

    Safety & Quality
    ----------------
    • Deduplication by canonical (s,p,o) key.
    • Enforcement of 'no new entities' when accepting Phase-1 outputs.
    • Bounded loop with `patience` early-stop to avoid infinite retries.

    Returns
    -------
    The list of *newly* added quadruples (not the full graph).
    """
    seen = {_quad_key(q) for q in initial_quads}
    all_q = initial_quads.copy()
    added: List[Quadruple] = []

    def _add_many(cands: List[Quadruple]) -> int:
        n = 0
        for q in cands:
            k = _quad_key(q)
            if k not in seen:
                seen.add(k); all_q.append(q); added.append(q); n += 1
        return n

    # ---- baseline ----
    cl0 = _cluster(all_q)
    print(f"🔍 START  : {len(all_q)} quads  |  {len(cl0)} clusters")

    # ---- phase-1 (filter to known entities for extra safety) ----
    allowed = _all_entity_names(all_q)
    phase1_raw = _phase1(paragraph, all_q)
    n1 = _add_many(_filter_to_known_entities(phase1_raw, allowed))
    cl1 = _cluster(all_q)
    print(f"🔍 AFTER-1: +{n1}  |  {len(cl1)} clusters")

    # ---- phase-2 ----
    n2 = _add_many(_phase2(paragraph, cl1, max_workers))
    cl2 = _cluster(all_q)
    print(f"🔍 AFTER-2: +{n2}  |  {len(cl2)} clusters")

    # ---- phase-3 (iterate until connected / stalled) ----
    if len(cl2) > 1:
        print("🔁 ENTERING PHASE-3 (iterative)")
        added_more, rounds = _phase3_iterate_until_connected(
            paragraph=paragraph,
            all_q=all_q,
            seen_keys=seen,
            max_workers=max_workers,
            max_rounds=max_rounds,
            patience=patience,
            run_global_pass_each_round=run_global_pass_each_round,
        )
        added.extend(added_more)
        print(f"🔁 PHASE-3 completed in {rounds} round(s) | +{len(added_more)} quads")

    # ---- verdict ----
    uniq_entities = {
        _canon(e) for q in all_q for e in (q['subject']['name'], q['object']['name'])
    }
    final_clusters = _cluster(all_q)
    print(f"📊 FINAL  : {len(all_q)} quads, {len(uniq_entities)} entities")

    if len(final_clusters) == 1:
        print("✅ SUCCESS – fully connected")
    else:
        print(f"⚠️ STILL {len(final_clusters)} components – check prompts / data")

    return added