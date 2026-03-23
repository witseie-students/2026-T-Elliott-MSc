# backend/knowledge_graph_generator/services.py
# Description: This file contains functions that are used within the management command create_knowledge_graph.py as well as to communicate with the api views.

import os
from django.conf import settings
import requests
from django.db import transaction

# ------------------------------
# PARAGRAPH PROCESSING SERVICE:
# ------------------------------

# OUPUT FORMAT:
"""
{
  "input_paragraph": "...",  
  "results": [
    {
      "proposition_sentence": "...",
      "coreferenced_sentence": "...",
      "quadruples": [
        {
          "quadruple": {
            "subject": { "name": "...", "types": [...] },
            "predicate": "...",
            "predicate_types": [...],
            "object": { "name": "...", "types": [...] },
            "reason": "..."
          },
          "natural_language_sentence": "...",
          "cosine_similarity": ...
        }
      ]
    }
  ],
  "propositions_paragraph": "...",
  "coreferenced_paragraph": "...",
  "natural_language_paragraph": "...",
  "similarities": {
    "propositions_similarity": ...,
    "coreferenced_similarity": ...,
    "natural_language_similarity": ...
  },
  "new_inferred_quadruples": [
    {
      "quadruple": {
        "subject": { "name": "...", "types": [...] },
        "predicate": "...",
        "predicate_types": [...],
        "object": { "name": "...", "types": [...] },
        "reason": "..."
      },
      "natural_language_sentence": "..."
    }
  ]
}
"""

def send_paragraph_to_processing_api(paragraph):
    """
    Sends a paragraph to the process_paragraph API endpoint for processing.
    :param paragraph: The input paragraph to process.
    :return: The response JSON containing the processed knowledge graph data or an error message.
    """
    url = "http://127.0.0.1:8000/api/process_paragraph/"  # Local server URL for the paragraph processing API
    headers = {'Authorization': 'Token 649ad111031dae78f9fdf80fce9ad07fbeaca812'}
    data = {'paragraph': paragraph}

    response = requests.post(url, headers=headers, json=data)  # Use `json=data` to ensure proper JSON formatting

    if response.status_code == 200:
        try:
            return response.json()
        except ValueError:
            print(f"Expected JSON response but got: {response.text}")
            return None
    else:
        try:
            error_message = response.json().get('error', 'No error message provided')
        except ValueError:
            error_message = response.text
        print(f"Error: {response.status_code} - {error_message}")
        return None

def send_paragraph_to_parallel_api(paragraph):
    url = "http://127.0.0.1:8000/api/process_paragraph_parallel/"
    headers = {"Authorization": "Token 649ad111031dae78f9fdf80fce9ad07fbeaca812"}
    response = requests.post(url, headers=headers, json={"paragraph": paragraph})
    return response.json() if response.status_code == 200 else None

