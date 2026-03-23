from knowledge_graph_generator.models import (
    Paragraph,
    Proposition,
    Quadruple,
    InferredQuadruple,
    EntityAlias,
)
from knowledge_graph_generator.chroma_db.operations import (
    add_entity,
    add_ontological_type,
    add_question,
)
from knowledge_graph_generator.chroma_db.entity_mapping import map_entity_to_canonical


def save_paragraph_to_db(knowledge_graph_json):
    """
    Save the knowledge graph JSON to the database and return paragraph + involved entity aliases + saved quadruples.
    """
    try:
        involved_entity_ids = set()

        # Step 1: Save the Paragraph
        paragraph_data = {
            "input_text": knowledge_graph_json.get("input_paragraph", ""),
            "propositions_paragraph": knowledge_graph_json.get("propositions_paragraph", ""),
            "coreferenced_paragraph": knowledge_graph_json.get("coreferenced_paragraph", ""),
            "natural_language_paragraph": knowledge_graph_json.get("natural_language_paragraph", ""),
            "propositions_similarity": knowledge_graph_json.get("similarities", {}).get("propositions_similarity"),
            "coreferenced_similarity": knowledge_graph_json.get("similarities", {}).get("coreferenced_similarity"),
            "natural_language_similarity": knowledge_graph_json.get("similarities", {}).get("natural_language_similarity"),
        }
        paragraph = Paragraph.objects.create(**paragraph_data)

        # Step 2: Process Propositions and Quadruples
        for proposition_data in knowledge_graph_json.get("results", []):
            proposition = Proposition.objects.create(
                paragraph=paragraph,
                text=proposition_data.get("proposition_sentence", ""),
                coreferenced_text=proposition_data.get("coreferenced_sentence", "")
            )

            for quadruple_data in proposition_data.get("quadruples", []):
                quad = quadruple_data.get("quadruple", {})
                quadruple = Quadruple.objects.create(
                    paragraph=paragraph,
                    proposition=proposition,
                    subject_name=quad.get("subject", {}).get("name", ""),
                    subject_types=quad.get("subject", {}).get("types", []),
                    predicate=quad.get("predicate", ""),
                    predicate_types=quad.get("predicate_types", []),
                    object_name=quad.get("object", {}).get("name", ""),
                    object_types=quad.get("object", {}).get("types", []),
                    reason=quad.get("reason", ""),
                    natural_language_sentence=quadruple_data.get("natural_language_sentence", ""),
                    cosine_similarity=quadruple_data.get("cosine_similarity"),
                    question=quadruple_data.get("question", ""),
                    answer_to_question=quadruple_data.get("answer_to_question", ""),
                    answer_similarity=quadruple_data.get("answer_similarity"),
                )

                # === Map entities to canonical ===
                subject_id = f"{quadruple.id}-subject"
                object_id = f"{quadruple.id}-object"

                map_entity_to_canonical(quadruple.subject_name, quadruple.id, role="subject")
                map_entity_to_canonical(quadruple.object_name, quadruple.id, role="object")

                involved_entity_ids.update([subject_id, object_id])

                # === Add to ChromaDB ===
                if quadruple.subject_name:
                    add_entity(subject_id, quadruple.subject_name, str(quadruple.id))
                if quadruple.object_name:
                    add_entity(object_id, quadruple.object_name, str(quadruple.id))

                for stype in quadruple.subject_types:
                    add_ontological_type(f"{quadruple.id}-stype-{stype}", stype, str(quadruple.id))
                for otype in quadruple.object_types:
                    add_ontological_type(f"{quadruple.id}-otype-{otype}", otype, str(quadruple.id))

                if quadruple.question:
                    add_question(f"{quadruple.id}-question", quadruple.question, str(quadruple.id))

        # Step 3: Save Inferred Quadruples
        inferred_output = []

        for inferred in knowledge_graph_json.get("new_inferred_quadruples", []):
            inferred_instance = InferredQuadruple.objects.create(
                paragraph=paragraph,
                subject_name=inferred.get("quadruple", {}).get("subject", {}).get("name", ""),
                subject_types=inferred.get("quadruple", {}).get("subject", {}).get("types", []),
                predicate=inferred.get("quadruple", {}).get("predicate", ""),
                predicate_types=inferred.get("quadruple", {}).get("predicate_types", []),
                object_name=inferred.get("quadruple", {}).get("object", {}).get("name", ""),
                object_types=inferred.get("quadruple", {}).get("object", {}).get("types", []),
                reason=inferred.get("quadruple", {}).get("reason", ""),
                natural_language_sentence=inferred.get("natural_language_sentence", ""),
            )

            inferred_output.append({
                "inferred_quadruple_id": str(inferred_instance.id),
                "quadruple": {
                    "subject": {
                        "name": inferred_instance.subject_name,
                        "types": inferred_instance.subject_types,
                    },
                    "predicate": inferred_instance.predicate,
                    "predicate_types": inferred_instance.predicate_types,
                    "object": {
                        "name": inferred_instance.object_name,
                        "types": inferred_instance.object_types,
                    },
                    "reason": inferred_instance.reason,
                },
                "question": "",
            })

        # Step 4: Prepare Aliases
        aliases = EntityAlias.objects.filter(id__in=involved_entity_ids)
        alias_data = [
            {
                "id": alias.id,
                "name": alias.name,
                "canonical_group_id": alias.canonical_group_id,
                "canonical_name": alias.canonical_group.get_canonical_name()
            }
            for alias in aliases
        ]

        # Step 5: Prepare saved quadruples
        quadruple_output = []
        for proposition in paragraph.propositions.all():
            q_list = []
            for quad in proposition.quadruples.all():
                q_list.append({
                    "quadruple_id": str(quad.id),
                    "quadruple": {
                        "subject": {"name": quad.subject_name, "types": quad.subject_types},
                        "predicate": quad.predicate,
                        "predicate_types": quad.predicate_types,
                        "object": {"name": quad.object_name, "types": quad.object_types},
                        "reason": quad.reason,
                    },
                    "question": quad.question,
                })
            quadruple_output.append({
                "quadruples": q_list
            })

        return paragraph, alias_data, quadruple_output, inferred_output

    except Exception as e:
        print(f"❌ Error in save_paragraph_to_db: {e}")
        return None
