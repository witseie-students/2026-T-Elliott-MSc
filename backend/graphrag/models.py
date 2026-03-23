# backend/graphrag/models.py

from django.db import models
import uuid

class Conversation(models.Model):
    """
    Represents a single conversation session.
    Each session can have multiple related questions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # ✅ Automatically updated on save

    def __str__(self):
        return f"Conversation {self.id}"


class Question(models.Model):
    """
    Represents a single user-submitted question in a conversation.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation,
        related_name='questions',
        on_delete=models.CASCADE
    )
    text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Question {self.id} in {self.conversation_id}"
