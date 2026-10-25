from app.integrations.embeddings.client import EmbeddingClient
from app.integrations.llm.client import LLMClient
from app.integrations.vector_store.client import VectorSearchClient


class RecommendationService:
    """Future pipeline: rewrite query -> embed -> search -> business ranking.

    PostgreSQL/pgvector is the intended vector adapter. Choose an embedding model,
    dimensions, distance metric and access filters before creating vector tables.
    No recommendation endpoint is exposed until that pipeline is implemented.
    """

    def __init__(self, llm: LLMClient, embeddings: EmbeddingClient, vectors: VectorSearchClient):
        self.llm = llm
        self.embeddings = embeddings
        self.vectors = vectors
