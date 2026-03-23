# backend/knowledge_graph_generator/apps.py

from django.apps import AppConfig

class KnowledgeGraphGeneratorConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'knowledge_graph_generator'

    def ready(self):
        # Remove task triggering code to avoid startup execution
        pass
