# core/detection.py - intention detection with paragraph chunking

import os
import re
from difflib import SequenceMatcher

from data.dataset import FR_WORDS, INTENTIONS_BY_ID, VOICE_MAPPING, intentions
from services.llm import ollama_call


STOP_WORDS = {
    "a", "an", "and", "are", "be", "before", "do", "for", "how", "i", "in",
    "is", "it", "me", "of", "on", "or", "please", "show", "the", "to", "with",
    "je", "la", "le", "les", "un", "une", "de", "des", "du", "et", "pour",
    "sur", "dans", "svp",
}

SERVICE_KEYWORDS = {
    "s1": ["voice", "vocal", "speak", "audio", "conversion", "voix", "record", "command"],
    "s2": ["protocol", "convert", "status", "operational", "retrieve", "logs", "history"],
    "s3": ["ar", "augmented", "reality", "visual", "inspect", "overlay", "sequence",
           "guidance", "glasses", "assembly", "procedure", "instructions"],
    "s4": ["content", "display", "show", "highlight", "summary", "overlay", "schematics"],
    "s5": ["error", "detect", "fault", "wear", "damage", "check", "verify", "alignment",
           "leak", "inconsistency"],
    "s6": ["anomaly", "analyze", "analysis", "vibration", "motor", "temperature",
           "pressure", "sensor", "load", "current", "predictive"],
}

ACTION_WORDS = {
    "retrieve", "show", "display", "highlight", "detect", "check", "verify", "analyze",
    "monitor", "provide", "generate", "perform", "capture", "send", "alert", "keep",
    "deploy", "activate", "inspect", "replace",
}


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.lower())).strip()


def tokenize(text: str) -> list[str]:
    return [w for w in normalize_text(text).split() if w and w not in STOP_WORDS]


def split_intent_chunks(text: str) -> list[str]:
    """Split a paragraph into ordered sub-requests before classification.

    The splitter is intentionally conservative: it uses sequencing connectors
    first, then splits commas only when the right side looks like a new action.
    Very short fragments are merged back into the previous chunk.
    """
    raw = re.sub(r"\s+", " ", (text or "").strip())
    if not raw:
        return []

    connector_pattern = re.compile(
        r"\b(?:(?:and\s+)?then|after\s+that|before\s+that|before\s+we|"
        r"(?:and\s+)?finally|(?:and\s+)?next|first|second|third)\b",
        flags=re.IGNORECASE,
    )

    protected = connector_pattern.sub(" <SPLIT> ", raw)
    first_pass = [p.strip(" ,.;:") for p in protected.split("<SPLIT>") if p.strip(" ,.;:")]

    chunks: list[str] = []
    for part in first_pass:
        comma_parts = [p.strip(" ,.;:") for p in re.split(r"\s*,\s*", part) if p.strip(" ,.;:")]
        if len(comma_parts) <= 1:
            chunks.append(part)
            continue

        current = comma_parts[0]
        for candidate in comma_parts[1:]:
            cand_words = set(tokenize(candidate))
            cur_words = tokenize(current)
            raw_candidate_words = set(normalize_text(candidate).split())
            looks_like_action = bool(raw_candidate_words & ACTION_WORDS)
            long_enough = len(cand_words) >= 3
            current_long = len(cur_words) >= 3
            if looks_like_action and long_enough and current_long:
                chunks.append(current)
                current = candidate
            else:
                current = f"{current}, {candidate}"
        chunks.append(current)

    cleaned: list[str] = []
    for chunk in chunks:
        chunk = chunk.strip(" ,.;:")
        if not chunk:
            continue
        # Avoid over-splitting fragments like "AR instructions", but keep short
        # action chunks such as "highlight errors" as independent requests.
        has_action = bool(set(normalize_text(chunk).split()) & ACTION_WORDS)
        if cleaned and len(tokenize(chunk)) < 3 and not has_action:
            cleaned[-1] = f"{cleaned[-1]} {chunk}".strip()
        else:
            cleaned.append(chunk)

    return cleaned or [raw]


def _intent_tokens(intent: dict) -> set[str]:
    return set(tokenize(intent["description"]))


def _phrase_score(text_norm: str, intent_id: str) -> tuple[float, str]:
    best = 0.0
    best_phrase = ""
    for phrase in VOICE_MAPPING.get(intent_id, []):
        phrase_norm = normalize_text(phrase)
        if not phrase_norm:
            continue
        if phrase_norm in text_norm:
            score = 8.0 + min(len(phrase_norm.split()), 4) * 0.8
        else:
            score = SequenceMatcher(None, phrase_norm, text_norm).ratio() * 5.0
        if score > best:
            best = score
            best_phrase = phrase
    return best, best_phrase


def score_intention(text: str, intent: dict) -> dict:
    text_norm = normalize_text(text)
    text_tokens = set(tokenize(text))
    desc_tokens = _intent_tokens(intent)
    services = intent["services"]

    phrase_score, phrase = _phrase_score(text_norm, intent["id"])
    overlap = text_tokens & desc_tokens
    overlap_ratio = len(overlap) / max(len(desc_tokens), 1)
    overlap_score = len(overlap) * 1.4 + overlap_ratio * 5.0

    service_hits = []
    for svc_id in services:
        kws = SERVICE_KEYWORDS.get(svc_id, [])
        if any(kw in text_tokens or kw in text_norm for kw in kws):
            service_hits.append(svc_id)
    service_score = min(len(service_hits) * 2.0, 4.0)

    broad_penalty = 0.0
    if len(services) >= 5 and phrase_score < 8:
        broad_penalty = 5.0
    elif len(services) >= 4 and phrase_score < 8:
        broad_penalty = 2.0

    score = max(0.0, phrase_score + overlap_score + service_score - broad_penalty)
    confidence = min(1.0, score / 14.0)

    return {
        "id": intent["id"],
        "intent": intent,
        "score": round(score, 2),
        "confidence": round(confidence, 2),
        "phrase": phrase,
        "overlap": sorted(overlap),
        "service_hits": service_hits,
    }


def rank_intentions(text: str, limit: int | None = None) -> list[dict]:
    ranked = [score_intention(text, intent) for intent in intentions]
    ranked = [r for r in ranked if r["score"] > 0]
    ranked.sort(key=lambda r: r["score"], reverse=True)
    return ranked[:limit] if limit else ranked


def compute_keyword_scores(text_lower: str) -> dict:
    # Kept for compatibility with older call sites/tests.
    return {r["id"]: r["score"] for r in rank_intentions(text_lower)}


def prefilter_intentions(text_lower: str, top_n: int = 10) -> list:
    return [r["intent"] for r in rank_intentions(text_lower, limit=top_n)]


def _print_ranked(ranked: list[dict], title: str = "Matching candidates"):
    print(f"\n   {title}:")
    for r in ranked[:5]:
        detail = []
        if r["phrase"]:
            detail.append(f"phrase='{r['phrase']}'")
        if r["overlap"]:
            detail.append(f"words={','.join(r['overlap'][:5])}")
        if r["service_hits"]:
            detail.append(f"svc={','.join(r['service_hits'])}")
        suffix = f" ({'; '.join(detail)})" if detail else ""
        print(f"      {r['id']} score={r['score']} conf={r['confidence']}{suffix}")


def _select_ranked(ranked: list[dict], max_intents: int) -> list:
    if not ranked:
        return []

    _print_ranked(ranked)
    top = ranked[0]
    second = ranked[1] if len(ranked) > 1 else None
    gap = top["score"] - second["score"] if second else top["score"]

    min_score = 5.0
    min_confidence = 0.35
    min_gap = 1.2

    if top["score"] < min_score or top["confidence"] < min_confidence:
        print(f"   No reliable intention: top score={top['score']} conf={top['confidence']}")
        return []
    if second and gap < min_gap and top["phrase"] == "":
        print(
            f"   Ambiguous request: {top['id']} and {second['id']} are too close "
            f"(gap={round(gap, 2)})"
        )
        return []

    selected = [top]
    used_svcs = set(top["intent"]["services"])

    for r in ranked[1:]:
        if len(selected) >= max_intents:
            break
        if r["score"] < 7.0 or r["confidence"] < 0.5:
            continue
        new_services = set(r["intent"]["services"]) - used_svcs
        if new_services:
            selected.append(r)
            used_svcs.update(r["intent"]["services"])

    print(
        "   Matched intentions: "
        + ", ".join(f"{r['id']}(conf={r['confidence']})" for r in selected)
    )
    return [r["intent"] for r in selected]


def keyword_fallback(text_lower: str, max_intents: int) -> list:
    return _select_ranked(rank_intentions(text_lower), max_intents)


def detect_with_ollama(text: str, text_lower: str) -> list:
    if os.getenv("IBN_SKIP_OLLAMA", "").lower() in {"1", "true", "yes"}:
        print("   Ollama skipped by IBN_SKIP_OLLAMA")
        return []

    candidates = prefilter_intentions(text_lower, top_n=8)
    if not candidates:
        return []

    candidate_ids = {i["id"] for i in candidates}
    print(f"   Prefiltered candidates: {sorted(candidate_ids)}")
    max_n = 1 if len(tokenize(text)) <= 6 else 3
    candidates_list = "\n".join(f"{i['id']}: {i['description']}" for i in candidates)
    prompt = f"""You are a classifier. Pick the BEST matching intention ID for the technician request.
OUTPUT: Only the ID(s) separated by commas. Example: i3
No explanations, no service codes, no dashes, no ranges.
MAX {max_n} ID(s).

CANDIDATE INTENTIONS:
{candidates_list}

TECHNICIAN REQUEST: {text}

BEST ID(s):"""
    try:
        raw = ollama_call(prompt, max_tokens=15)
        answer = raw.replace("\n", ",").replace(" ", "").lower()
        print(f"   Ollama -> {answer}")
        found_ids = list(dict.fromkeys(re.findall(r"i\d+", answer)))[:max_n]
        detected = []
        ranked_by_id = {r["id"]: r for r in rank_intentions(text)}
        top_score = max((r["score"] for r in ranked_by_id.values()), default=0)
        for iid in found_ids:
            if iid not in candidate_ids:
                print(f"   Ollama proposed invalid candidate {iid}; ignored")
                continue
            local_score = ranked_by_id.get(iid, {}).get("score", 0)
            if top_score and local_score < top_score * 0.55:
                print(f"   Ollama {iid} rejected by local score ({local_score} vs top {top_score})")
                continue
            intent = INTENTIONS_BY_ID.get(iid)
            if intent:
                detected.append(intent)
        return detected
    except Exception as e:
        print(f"   Ollama error: {e}")
        return []


def _detect_single_block(text: str, max_intents: int | None = None) -> list:
    text_norm = normalize_text(text)
    is_french = len(set(text_norm.split()) & FR_WORDS) >= 1
    if max_intents is None:
        max_intents = 1 if len(tokenize(text)) <= 6 else 3

    ranked = rank_intentions(text)
    if is_french:
        print("\n   Language FR -> explainable keyword matching")
        return _select_ranked(ranked, max_intents)

    print("\n   Language EN -> local ranking + optional Ollama validation")
    local = _select_ranked(ranked, max_intents)
    ollama_detected = detect_with_ollama(text, text_norm)

    if not ollama_detected:
        return local

    local_ids = {i["id"] for i in local}
    ollama_ids = {i["id"] for i in ollama_detected}
    if local_ids & ollama_ids:
        print(f"   Ollama agrees with local match: {sorted(local_ids & ollama_ids)}")
        return local

    if local:
        print(f"   Ollama disagreement ignored; keeping local match {sorted(local_ids)}")
        return local
    return ollama_detected


def detect_multiple_intentions(text: str) -> list:
    """Detect ordered intentions from a single command or a multi-request paragraph."""
    print(f"\nOriginal request: {text}")
    chunks = split_intent_chunks(text)
    print(f"Detected chunks ({len(chunks)}):")
    for idx, chunk in enumerate(chunks, 1):
        print(f"   chunk {idx}: {chunk}")

    merged: list[dict] = []
    seen_ids = set()
    multi_chunk = len(chunks) > 1

    for idx, chunk in enumerate(chunks, 1):
        # Default to one best intent per chunk. Allow more only for long chunks
        # that still look like they contain several actions.
        action_count = len(set(tokenize(chunk)) & ACTION_WORDS)
        max_for_chunk = 1
        if len(tokenize(chunk)) >= 12 and action_count >= 2:
            max_for_chunk = 2
        if not multi_chunk and len(tokenize(chunk)) >= 18:
            max_for_chunk = 3

        print(f"\nChunk {idx} detection (max={max_for_chunk}): {chunk}")
        detected = _detect_single_block(chunk, max_intents=max_for_chunk)
        ids = [intent["id"] for intent in detected]
        print(f"Chunk {idx} -> detected {ids if ids else 'none'}")

        for intent in detected:
            if intent["id"] in seen_ids:
                print(f"   duplicate {intent['id']} ignored")
                continue
            merged.append(intent)
            seen_ids.add(intent["id"])

    print(f"Final merged intentions -> {[intent['id'] for intent in merged]}")
    return merged


def detect_intention(text: str):
    results = detect_multiple_intentions(text)
    return results[0] if results else None
