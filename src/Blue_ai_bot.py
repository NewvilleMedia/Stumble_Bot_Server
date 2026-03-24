from persona_config import BLUE_SYSTEM_PROMPT, POETRY_RULE
from model_config import model
from engagement_prompts import get_engagement_prompt

RELATIONSHIP_EMPHASIS = """
RELATIONSHIP EMPHASIS (ACTIVATED):
This message is about a relationship. You MUST:
- Focus on attachment patterns, communication dynamics, and boundaries
- Ask about what they need vs what they're tolerating
- Frame everything through relational dynamics, not general advice
- Explore the space between what they want and what they're getting
- Help them see patterns in how they connect with others
"""


def blue(user_input, relationship_context=False, engagement_context=None):

    system_prompt = BLUE_SYSTEM_PROMPT
    if relationship_context:
        system_prompt += RELATIONSHIP_EMPHASIS
        print("💕 Relationship emphasis activated for Blue")

    engagement_section = get_engagement_prompt(engagement_context)
    if engagement_section:
        system_prompt += engagement_section
        print(f"🎮 Engagement L{engagement_context.get('stretch_level', 1)} for Blue")

    # Style instruction from engagement_context
    if engagement_context and engagement_context.get('style_instruction'):
        system_prompt += f"\nRESPONSE STYLE:\n{engagement_context['style_instruction']}\nYou MUST include poetic, symbolic, or mythic language in at least one line of your response.\n"

    # Always include poetry/voice depth rule
    system_prompt += POETRY_RULE
    system_prompt += "\n\nTARGETING RULE: You are responding to exactly ONE user message. Never reference multiple users, summarize a thread, or address the group. Respond directly and personally to the specific message you receive."

    try:
        response = model.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_input}
            ]
        )

        print(response.choices[0].message.content)
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error: {e}")
        return "Sorry, something went wrong."
