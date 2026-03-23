# backend/knowledge_graph_generator/urls.py

from django.urls import path
from . import views

urlpatterns = [
    path('process_paragraph/', views.ProcessParagraphView.as_view(), name='process_paragraph'),
    path("process_paragraph_parallel/", views.ProcessParagraphParallelView.as_view(), name="process_paragraph_parallel"),
]
