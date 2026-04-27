import json
import re
from dataclasses import dataclass
from pathlib import Path

import faiss
import numpy as np
from rapidfuzz import fuzz
from sentence_transformers import SentenceTransformer


@dataclass
class SearchResult:
    item: dict
    question: str
    faiss_score: float
    fuzzy_score: float
    confidence: float
    exact_match: bool = False


class RAGService:
    def __init__(
        self,
        dataset_path: Path,
        storage_dir: Path,
        model_name: str = "all-MiniLM-L6-v2",
        dataset_confidence_threshold: float = 0.70,
        fuzzy_threshold: float = 0.75,
        semantic_threshold: float = 0.70,
    ):
        self.dataset_path = dataset_path
        self.storage_dir = storage_dir
        self.model_name = model_name
        self.dataset_confidence_threshold = dataset_confidence_threshold
        self.fuzzy_threshold = fuzzy_threshold
        self.semantic_threshold = semantic_threshold
        self.index_path = storage_dir / "faiss_index.bin"
        self.embeddings_path = storage_dir / "embeddings.npy"
        self.dataset = self._load_dataset()
        self.index_items: list[dict] = []
        self.model: SentenceTransformer | None = None
        self.index: faiss.Index | None = None
        self._build_index()

    def _load_dataset(self) -> list[dict]:
        with self.dataset_path.open("r", encoding="utf-8") as file:
            return json.load(file)

    def _build_index(self) -> None:
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.index_items = self._create_index_items()
        texts = [item["text"] for item in self.index_items]

        self.model = SentenceTransformer(self.model_name)

        if self.index_path.exists() and self.embeddings_path.exists():
            vectors = np.load(self.embeddings_path)
            self.index = faiss.read_index(str(self.index_path))
            if self.index.ntotal == len(self.index_items):
                return

        vectors = self.model.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
            show_progress_bar=True,
        ).astype(np.float32)

        self.index = faiss.IndexFlatIP(vectors.shape[1])
        self.index.add(vectors)
        np.save(self.embeddings_path, vectors)
        faiss.write_index(self.index, str(self.index_path))

    def _create_index_items(self) -> list[dict]:
        items = []
        for row in self.dataset:
            items.append(
                {
                    "dataset_id": row.get("id"),
                    "language": "en",
                    "question": row.get("question_en", ""),
                    "text": f"{row.get('question_en', '')} {row.get('answer_en', '')}",
                    "item": row,
                }
            )

            if row.get("question_fr"):
                items.append(
                    {
                        "dataset_id": row.get("id"),
                        "language": "fr",
                        "question": row.get("question_fr", ""),
                        "text": f"{row.get('question_fr', '')} {row.get('answer_fr', '')}",
                        "item": row,
                    }
                )
        return items

    def answer(self, question: str, language: str) -> tuple[dict, dict]:
        matches = self.search(question, language, top_k=5)
        best = matches[0] if matches else None
        suggestions = [match.question for match in matches[:3]]

        if not best:
            response = {
                "answer": "",
                "category": None,
                "risk": None,
                "follow_up": None,
                "confidence": 0.0,
                "language": language,
                "suggestions": [],
                "source": "dataset",
                "fallback_used": False,
                "matched_question": None,
            }
            meta = {
                "matched_question": None,
                "dataset_match": False,
                "suggestions": [],
            }
            return response, meta

        item = best.item
        dataset_match = self._is_good_dataset_match(best)
        response = {
            "answer": self._answer_for_language(item, language) if dataset_match else "",
            "category": item.get("category"),
            "risk": item.get("risk_level"),
            "follow_up": self._follow_up_for_language(item, language) if dataset_match else None,
            "confidence": round(best.confidence, 2),
            "language": language,
            "suggestions": [] if dataset_match else suggestions,
            "source": "dataset",
            "fallback_used": False,
            "matched_question": best.question,
        }
        meta = {
            "matched_question": best.question,
            "dataset_match": dataset_match,
            "suggestions": suggestions,
        }
        return response, meta

    def search(self, question: str, language: str, top_k: int = 5) -> list[SearchResult]:
        exact_match = self._find_exact_or_near_exact_match(question, language)
        if exact_match:
            return [exact_match]

        if self.model is None or self.index is None:
            return self._fuzzy_only_search(question, language, top_k)

        query_vector = self.model.encode(
            [question],
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype(np.float32)
        faiss_scores, indices = self.index.search(query_vector, min(top_k * 4, len(self.index_items)))

        candidates: dict[int, SearchResult] = {}
        for raw_score, idx in zip(faiss_scores[0], indices[0]):
            if idx < 0:
                continue

            index_item = self.index_items[idx]
            item = index_item["item"]
            fuzzy_score = self._best_fuzzy_score(question, item, language)
            faiss_score = self._normalize_faiss_score(float(raw_score))
            combined_score = self._combine_scores(faiss_score, fuzzy_score)
            confidence = max(combined_score, faiss_score, fuzzy_score)
            dataset_id = item.get("id", idx)

            current = candidates.get(dataset_id)
            result = SearchResult(
                item=item,
                question=self._question_for_language(item, language),
                faiss_score=faiss_score,
                fuzzy_score=fuzzy_score,
                confidence=confidence,
            )
            if current is None or result.confidence > current.confidence:
                candidates[dataset_id] = result

        for item in self.dataset:
            fuzzy_score = self._best_fuzzy_score(question, item, language)
            if fuzzy_score < 0.35:
                continue
            dataset_id = item.get("id")
            current = candidates.get(dataset_id)
            combined_score = self._combine_scores(0.0, fuzzy_score)
            confidence = max(combined_score, fuzzy_score)
            result = SearchResult(
                item=item,
                question=self._question_for_language(item, language),
                faiss_score=0.0,
                fuzzy_score=fuzzy_score,
                confidence=confidence,
            )
            if current is None or result.confidence > current.confidence:
                candidates[dataset_id] = result

        return sorted(candidates.values(), key=lambda result: result.confidence, reverse=True)[:top_k]

    def _find_exact_or_near_exact_match(self, question: str, language: str) -> SearchResult | None:
        user_question = self._normalize_question(question)
        if not user_question:
            return None

        best: SearchResult | None = None
        for item in self.dataset:
            candidates = [
                ("en", item.get("question_en", "")),
                ("fr", item.get("question_fr", "")),
            ]

            for candidate_language, candidate_question in candidates:
                normalized_candidate = self._normalize_question(candidate_question)
                if not normalized_candidate:
                    continue

                if user_question == normalized_candidate:
                    return SearchResult(
                        item=item,
                        question=candidate_question,
                        faiss_score=1.0,
                        fuzzy_score=1.0,
                        confidence=1.0,
                        exact_match=True,
                    )

                ratio = fuzz.ratio(user_question, normalized_candidate) / 100
                token_ratio = fuzz.token_set_ratio(user_question, normalized_candidate) / 100
                near_exact_score = max(ratio, token_ratio)
                if near_exact_score >= 0.95:
                    result = SearchResult(
                        item=item,
                        question=candidate_question,
                        faiss_score=1.0,
                        fuzzy_score=near_exact_score,
                        confidence=near_exact_score,
                        exact_match=False,
                    )
                    if best is None or result.confidence > best.confidence:
                        best = result

        return best

    def _fuzzy_only_search(self, question: str, language: str, top_k: int) -> list[SearchResult]:
        results = []
        for item in self.dataset:
            fuzzy_score = self._best_fuzzy_score(question, item, language)
            results.append(
                SearchResult(
                    item=item,
                    question=self._question_for_language(item, language),
                    faiss_score=0.0,
                    fuzzy_score=fuzzy_score,
                    confidence=fuzzy_score,
                )
            )
        return sorted(results, key=lambda result: result.confidence, reverse=True)[:top_k]

    def _best_fuzzy_score(self, question: str, item: dict, language: str) -> float:
        user_text = question.lower().strip()
        canonical_user_text = self._canonical_text(user_text)
        query_tokens = self._tokens(user_text)
        canonical_query_tokens = self._tokens(canonical_user_text)
        candidate_questions = [item.get("question_en", "")]

        if item.get("question_fr"):
            candidate_questions.append(item["question_fr"])
        if language == "ar":
            candidate_questions.append(item.get("answer_en", ""))

        best_score = 0.0
        for candidate in candidate_questions:
            candidate_text = candidate.lower().strip()
            canonical_candidate_text = self._canonical_text(candidate_text)
            candidate_tokens = self._tokens(candidate_text)
            canonical_candidate_tokens = self._tokens(canonical_candidate_text)
            ratio = fuzz.ratio(user_text, candidate_text) / 100
            token_ratio = fuzz.token_set_ratio(user_text, candidate_text) / 100
            overlap = (
                len(query_tokens & candidate_tokens) / max(len(query_tokens | candidate_tokens), 1)
                if query_tokens and candidate_tokens
                else 0.0
            )
            canonical_ratio = fuzz.ratio(canonical_user_text, canonical_candidate_text) / 100
            canonical_token_ratio = fuzz.token_set_ratio(canonical_user_text, canonical_candidate_text) / 100
            canonical_overlap = (
                len(canonical_query_tokens & canonical_candidate_tokens)
                / max(len(canonical_query_tokens | canonical_candidate_tokens), 1)
                if canonical_query_tokens and canonical_candidate_tokens
                else 0.0
            )
            raw_score = (ratio * 0.25) + (token_ratio * 0.55) + (overlap * 0.20)
            canonical_score = (
                (canonical_ratio * 0.25)
                + (canonical_token_ratio * 0.55)
                + (canonical_overlap * 0.20)
            )
            score = max(raw_score, canonical_score)
            best_score = max(best_score, score)
        return best_score

    def _combine_scores(self, faiss_score: float, fuzzy_score: float) -> float:
        return max(0.0, min((faiss_score * 0.65) + (fuzzy_score * 0.35), 1.0))

    def _is_good_dataset_match(self, result: SearchResult) -> bool:
        return (
            result.exact_match
            or result.fuzzy_score >= self.fuzzy_threshold
            or result.faiss_score >= self.semantic_threshold
            or result.confidence >= self.dataset_confidence_threshold
        )

    def _normalize_faiss_score(self, score: float) -> float:
        return max(0.0, min(score, 1.0))

    def _tokens(self, text: str) -> set[str]:
        return set(re.findall(r"\b\w{3,}\b", text.lower(), flags=re.UNICODE))

    def _normalize_question(self, text: str) -> str:
        lowered = text.lower().strip()
        without_punctuation = re.sub(r"[^\w\s]", " ", lowered, flags=re.UNICODE)
        return re.sub(r"\s+", " ", without_punctuation).strip()

    def _canonical_text(self, text: str) -> str:
        normalized = self._normalize_question(text)
        replacements = {
            "is it okay to": "can i",
            "is it ok to": "can i",
            "am i allowed to": "can i",
            "with power on": "live",
            "power on": "live",
            "powered on": "live",
            "energized": "live",
            "energised": "live",
            "electrical wires": "wires",
            "electric wires": "wires",
            "cables": "wires",
            "check": "test",
            "inspect": "test",
        }
        for source, target in replacements.items():
            normalized = re.sub(rf"\b{re.escape(source)}\b", target, normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    def _answer_for_language(self, item: dict, language: str) -> str:
        if language == "fr" and item.get("answer_fr"):
            return item["answer_fr"]
        return item.get("answer_en", "")

    def _follow_up_for_language(self, item: dict, language: str) -> str:
        if language == "fr" and item.get("follow_up_fr"):
            return item["follow_up_fr"]
        return item.get("follow_up_en", "")

    def _question_for_language(self, item: dict, language: str) -> str:
        if language == "fr" and item.get("question_fr"):
            return item["question_fr"]
        return item.get("question_en", "")

    @property
    def indexed_count(self) -> int:
        return len(self.index_items)
