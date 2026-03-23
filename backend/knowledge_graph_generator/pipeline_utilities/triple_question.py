from pydantic import BaseModel
from openai import OpenAI
from django.conf import settings

# -----------------------------------------
# Set up the OpenAI client with your API key
# -----------------------------------------
client = OpenAI(api_key=settings.OPENAI_API_KEY)

# -----------------------------------------
# Pydantic Models for Input Validation
# -----------------------------------------

class Entity(BaseModel):
    name: str
    types: list[str]

class QuadrupleWithEntityTypes(BaseModel):
    subject: Entity
    predicate: str
    predicate_types: list[str]
    object: Entity
    reason: str

# -----------------------------------------
# Function to Convert Quadruple to Question
# -----------------------------------------

def quadruple_to_question(quadruple: dict) -> str:
    """
    Converts a knowledge quadruple into a natural-sounding question.
    The question should be precisely answered by the quadruple itself.

    :param quadruple: Dictionary representing a quadruple with entity and predicate types.
    :return: A natural language question.
    """
    model = "gpt-4.1-nano"

    subject = quadruple["subject"]["name"]
    predicate = quadruple["predicate"]
    obj = quadruple["object"]["name"]
    reason = quadruple.get("reason", "")

    prompt = (
        "You are a question-generation assistant. Your job is to take a knowledge quadruple and generate a single "
        "natural-language question that would be precisely and completely answered by the information in the quadruple.\n\n"
        f"Here is the quadruple:\n"
        f"Subject: {subject}\n"
        f"Predicate: {predicate}\n"
        f"Object: {obj}\n"
        f"Reason: {reason}\n\n"
        "Write a question that someone might ask to which this exact quadruple would be the complete answer."
    )

    try:
        completion = client.beta.chat.completions.parse(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": "You generate precise questions from structured knowledge data."},
                {"role": "user", "content": prompt}
            ]
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating question from quadruple: {e}")
        return None


# -----------------------------------------
# Function to Convert Question to Answer Sentence
# -----------------------------------------

def question_to_sentence(question: str) -> str:
    """
    Converts a natural language question into a natural-sounding answer sentence.

    This function is useful for generating declarative sentences from questions
    where the answer is known or implied.

    :param question: A natural language question.
    :return: A natural language sentence that answers the question.
    """
    model = "gpt-4o-mini"

    system_prompt = (
        "You are an assistant that generates natural-sounding declarative sentences "
        "that directly and completely answer user questions. The sentence should be informative and self-contained."
        "The answer should be a single sentence."
    )

    user_prompt = (
        f"Question: {question}\n\n"
        "Write a complete, natural-sounding sentence that answers the question."
    )

    try:
        completion = client.beta.chat.completions.parse(
            model=model,
            temperature=0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"Error generating sentence from question: {e}")
        return None


# -----------------------------------------
# Example Usage
# -----------------------------------------

if __name__ == "__main__":
    example_quadruple = {
        "subject": {"name": "Insulin", "types": ["Protein", "Hormone"]},
        "predicate": "regulates",
        "predicate_types": ["Biological Process"],
        "object": {"name": "blood glucose levels", "types": ["Biological Parameter"]},
        "reason": "Insulin helps maintain homeostasis by lowering blood sugar."
    }

    question = quadruple_to_question(example_quadruple)
    print("Generated Question:")
    print(question)

    follow_up_question = question
    sentence = question_to_sentence(follow_up_question)
    print("\nGenerated Sentence:")
    print(sentence)

