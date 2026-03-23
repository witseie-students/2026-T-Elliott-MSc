# knowledge_graph_generator/chroma_db/embedding.py

from typing import List

from sentence_transformers import SentenceTransformer

# ------------------------------------------------------------------ #
#  Model loading (happens once at import)
# ------------------------------------------------------------------ #
# • Loading tens of MB can take a second, so we do it at module load
#   time and keep a single shared instance.
# • Feel free to swap the model name via env-var or settings module
#   if you need configurability.
transformer_model: SentenceTransformer = SentenceTransformer(
    "paraphrase-MiniLM-L6-v2"
)
# ------------------------------------------------------------------ #
#  Public API
# ------------------------------------------------------------------ #
def get_embedding(text: str, model: SentenceTransformer = transformer_model) -> List[float]:
    """
    Compute a sentence embedding.

    Parameters
    ----------
    text : str
        The input string you want to embed.
    model : SentenceTransformer, optional
        A *loaded* SentenceTransformer model. Defaults to the global
        `transformer_model`, but you can pass another instance to override.

    Returns
    -------
    List[float]
        A 384-dimensional embedding vector (as a Python list of floats).

    Raises
    ------
    RuntimeError
        If encoding fails for any reason.
    """
    if not isinstance(text, str):
        raise TypeError("`text` must be of type str")

    try:
        # encode() → numpy.ndarray; convert to list for parity with old API
        vec = model.encode(text, show_progress_bar=False, convert_to_numpy=True)
        return vec.tolist()
    except Exception as err:
        raise RuntimeError(f"Failed to generate embedding: {err}") from err







# -------------------
# ---- OLD CODE: ----
# -------------------

from openai import OpenAI

# Initialize the OpenAI client
client = OpenAI(api_key="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")

def get_embedding_LLM(text: str, model: str = "text-embedding-3-small") -> list:
    """
    Generate a vector embedding for the given text using OpenAI.
    
    :param text: The input string to embed.
    :param model: The embedding model to use (default: "text-embedding-3-small").
    :return: A list of floats representing the embedding vector.
    """
    try:
        response = client.embeddings.create(
            input=text,
            model=model
        )
        return response.data[0].embedding
    except Exception as e:
        raise RuntimeError(f"Failed to generate embedding: {e}")
