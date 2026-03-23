# backend/graphrag/admin.py

from django.contrib import admin
from .models import Conversation, Question

class QuestionInline(admin.TabularInline):
    model = Question
    extra = 0
    readonly_fields = ('id', 'text', 'created_at')

@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at')
    inlines = [QuestionInline]
    readonly_fields = ('id', 'created_at')
    search_fields = ('id',)

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ('id', 'conversation', 'text', 'created_at')
    readonly_fields = ('id', 'created_at')
    search_fields = ('id', 'text')
