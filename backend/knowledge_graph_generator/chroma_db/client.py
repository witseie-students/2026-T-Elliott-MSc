# knowledge_graph_generator/chroma_db/client.py


import os
import chromadb
from chromadb import PersistentClient

# Path to store the Chroma vector database
CHROMA_DB_DIR = os.path.join(os.getcwd(), "knowledge_graph_vector_db")

# Initialize a persistent Chroma DB client
client = PersistentClient(path=CHROMA_DB_DIR)

# Get or create collections
entity_collection = client.get_or_create_collection(name="entities")
ontological_type_collection = client.get_or_create_collection(name="ontological_types")
question_collection = client.get_or_create_collection(name="questions") 



