import logging
from typing import List
import torch
from sentence_transformers import SentenceTransformer, util

logger = logging.getLogger(__name__)


class SemanticMatcher:
    def __init__(
        self,
        keywords: List[str],
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ) -> None:
        self.keywords = keywords
        logger.info(f"Loading embedding model: {model_name}...")
        self.model = SentenceTransformer(model_name)

        # Automatically builds a semantic profile from your 3 keyphrases
        joined_keywords = ", ".join(self.keywords)
        self.target_profile_text = (
            f"Target Internship Roles: {joined_keywords}. "
            f"Seeking an undergraduate internship in Software Engineering, "
            f"Software Development, or AI Engineering involving Python, "
            f"backend and full-stack software development, APIs, cloud services, "
            f"machine learning, artificial intelligence, LLMs, and data structures."
        )
        self.target_embedding = self._encode_long_text(self.target_profile_text)
        logger.info(f"Semantic matcher initialized for: {joined_keywords}")

    def _encode_long_text(
        self, text: str, chunk_words: int = 180, overlap: int = 40
    ) -> torch.Tensor:
        words = text.split()
        if len(words) <= chunk_words:
            return self.model.encode(
                text, convert_to_tensor=True, normalize_embeddings=True
            )

        chunks: List[str] = []
        step = max(1, chunk_words - overlap)
        for i in range(0, len(words), step):
            chunk = " ".join(words[i : i + chunk_words])
            if chunk:
                chunks.append(chunk)

        chunk_embeddings = self.model.encode(
            chunks, convert_to_tensor=True, normalize_embeddings=True
        )
        mean_embedding = torch.mean(chunk_embeddings, dim=0)
        return torch.nn.functional.normalize(mean_embedding, p=2, dim=0)

    def compute_similarity(self, job_title: str, job_description: str) -> float:
        combined_job_text = f"{job_title}\n\n{job_description}"
        job_embedding = self._encode_long_text(combined_job_text)
        score_tensor = util.cos_sim(self.target_embedding, job_embedding)
        base_score = float(score_tensor.item())

        # Boost score if the job title directly matches one of your 3 keyphrases
        title_lower = job_title.lower()
        for phrase in ["software engineer", "software develop", "ai engineer", "artificial intelligence"]:
            if phrase in title_lower:
                base_score += 0.12
                break

        return round(max(0.0, min(1.0, base_score)), 4)