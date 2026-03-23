# backend/knowledge_graph_generator/management/commands/initiate_chroma_vectors.py
# Explanation: This code initializes the Chroma vector collections for entities, ontological types, and questions. It ensures that the collections are created using the PersistentClient from the chromadb library. The command can be run using Django's management command system.

from django.core.management.base import BaseCommand
from knowledge_graph_generator.chroma_db import client

class Command(BaseCommand):
    help = "Initializes Chroma vector collections for entities, ontological types, and questions."

    def handle(self, *args, **options):
        # This command simply ensures the collections are created using PersistentClient
        # The actual creation logic is triggered by importing the collections from `client.py`

        # Force the import to ensure collections are created
        _ = client.entity_collection
        _ = client.ontological_type_collection
        _ = client.question_collection

        self.stdout.write(self.style.SUCCESS("✅ Chroma vector collections initialized!"))
        self.stdout.write(self.style.SUCCESS("📁 Directory: knowledge_graph_vector_db"))
        self.stdout.write(self.style.SUCCESS("📦  - entities"))
        self.stdout.write(self.style.SUCCESS("📦  - ontological_types"))
        self.stdout.write(self.style.SUCCESS("📦  - questions"))
