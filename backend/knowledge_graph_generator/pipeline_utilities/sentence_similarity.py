from sentence_transformers import SentenceTransformer, util
import torch

# Load the SentenceTransformer model
transformer_model = SentenceTransformer('paraphrase-MiniLM-L6-v2')

def compute_similarity(sentence1, sentence2):
    """
    Compute the cosine similarity between two sentences using a SentenceTransformer model.
    If the similarity is negative, set it to 0.
    
    :param sentence1: First sentence.
    :param sentence2: Second sentence.
    :return: Cosine similarity score (>= 0).
    """
    try:
        # Generate embeddings for the sentences
        embedding1 = transformer_model.encode(sentence1, convert_to_tensor=True)
        embedding2 = transformer_model.encode(sentence2, convert_to_tensor=True)

        # Compute cosine similarity
        similarity = util.cos_sim(embedding1, embedding2).item()

        # Ensure non-negative similarity
        return max(similarity, 0)
    except Exception as e:
        print(f"Error computing similarity: {e}")
        return None


@torch.no_grad()
def compute_similarities_batch(anchor: str, others: dict[str, str]) -> dict[str, float]:
    """
    Compute cosine similarity between anchor and each text in `others`.
    Returns a dict keyed like `others`.
    """
    # encode in one go (normalize for fast dot similarity)
    all_texts = [anchor] + list(others.values())
    embs = transformer_model.encode(
        all_texts,
        convert_to_tensor=True,
        normalize_embeddings=True,
    )
    anchor_emb = embs[0]
    other_embs = embs[1:]

    sims = util.cos_sim(anchor_emb, other_embs).cpu().numpy().flatten().tolist()
    return {k: max(v, 0.0) for k, v in zip(others.keys(), sims)}