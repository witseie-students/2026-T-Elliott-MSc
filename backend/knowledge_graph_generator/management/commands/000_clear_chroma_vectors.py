# backend/knowledge_graph_generator/management/commands/clear_chroma_vectors.py

from django.core.management.base import BaseCommand
from knowledge_graph_generator.chroma_db import client


class Command(BaseCommand):
    help = "Clears all data from the Chroma vector collections (entities, ontological types, and questions)."

    def handle(self, *args, **options):
        entity_collection = client.entity_collection
        ontological_type_collection = client.ontological_type_collection
        question_collection = client.question_collection

        def clear_collection(name, collection):
            existing_ids = collection.get()['ids']
            if existing_ids:
                collection.delete(ids=existing_ids)
                self.stdout.write(self.style.SUCCESS(f"🧹 Cleared '{name}' collection ({len(existing_ids)} items removed)"))
            else:
                self.stdout.write(self.style.WARNING(f"ℹ️  '{name}' collection already empty."))

        clear_collection("entities", entity_collection)
        clear_collection("ontological_types", ontological_type_collection)
        clear_collection("questions", question_collection)

        self.stdout.write(self.style.SUCCESS("✅ All Chroma vector collections cleared."))
