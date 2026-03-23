# knowledge_graph_generator/chroma_db/operations.py

from .client import client, entity_collection, ontological_type_collection, question_collection

from .embedding import get_embedding


# -------------------------------
# ADD ENTITIES TO VECTOR DATABASE
# -------------------------------

def add_entity(entity_id: str, name: str, quadruple_id: str):
    """
    Add an entity to the Chroma entity collection.
    
    :param entity_id: Unique ID for the entity in the Chroma DB.
    :param name: The name of the entity (used for embedding).
    :param quadruple_id: The associated quadruple ID.
    """
    embedding = get_embedding(name)
    entity_collection.add(
        ids=[entity_id],
        embeddings=[embedding],
        metadatas=[{
            "entity_id": entity_id,  # ✅ Include this so it can be retrieved on match
            "quadruple_id": quadruple_id,
            "name": name
        }],
        documents=[name]
    )

# ----------------------------------------
# ADD ONTOLOGICAL TYPES TO VECTOR DATABASE
# ----------------------------------------

def add_ontological_type(type_id: str, type_name: str, quadruple_id: str):
    """
    Add an ontological type to the Chroma ontological_types collection.
    
    :param type_id: Unique ID for the ontological type in the Chroma DB.
    :param type_name: The type name (used for embedding).
    :param quadruple_id: The associated quadruple ID.
    """
    embedding = get_embedding(type_name)
    ontological_type_collection.add(
        ids=[type_id],
        embeddings=[embedding],
        metadatas=[{"quadruple_id": quadruple_id, "name": type_name}],
        documents=[type_name]
    )

# -------------------------------
# ADD QUESTION TO VECTOR DATABASE
# -------------------------------

def add_question(question_id: str, question_text: str, quadruple_id: str):
    """
    Add a question to the Chroma questions collection.
    
    :param question_id: Unique ID for the question in the Chroma DB.
    :param question_text: The actual question text.
    :param quadruple_id: The associated quadruple ID.
    """
    embedding = get_embedding(question_text)
    question_collection.add(
        ids=[question_id],
        embeddings=[embedding],
        metadatas=[{"quadruple_id": quadruple_id, "question": question_text}],
        documents=[question_text]
    )

# --------------------------
# CLEAR VECTOR DATABASE
# ---------------------------

def clear_chroma_collections(verbose: bool = True):
    """
    Clears all documents from the ChromaDB vector collections: entities, ontological types, and questions.
    """
    def clear_collection(name, collection):
        existing_ids = collection.get()['ids']
        if existing_ids:
            collection.delete(ids=existing_ids)
            if verbose:
                print(f"🧹 Cleared '{name}' collection ({len(existing_ids)} items removed)")
        elif verbose:
            print(f"ℹ️  '{name}' collection already empty.")

    clear_collection("entities", entity_collection)
    clear_collection("ontological_types", ontological_type_collection)
    clear_collection("questions", question_collection)

    if verbose:
        print("✅ All Chroma vector collections cleared.")