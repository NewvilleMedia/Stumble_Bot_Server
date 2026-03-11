from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from persona_config import (
    BOT_PERSONAS,
    EVENT_GUIDELINES,
)
from model_config import model
from routes import router as api_router
from engagement_prompts import get_engagement_prompt

# --------------------------
#  CONFIG
# --------------------------



app = FastAPI()


app.include_router(api_router, prefix="/api/v1")


# --------------------------
# SAFETY CLASSIFIER PROMPT
# --------------------------

SAFETY_CLASSIFIER_PROMPT = """
You are a safety classifier. 
Your job is ONLY to determine whether this message expresses
any level of:
- Suicide intent
- Wanting to die
- Self-harm
- Desire to disappear
- Hopelessness + desire to end life
- Phrases like "I can't do this anymore"
- Questions about suicide or self-harm

Reply with EXACTLY one word:
"YES" → If there is ANY self-harm risk.
"NO"  → If safe.

User message:
"{text}"
"""


def extract_all_text(data):
    """Recursively extract all text from nested dict/list structure."""
    texts = []
    
    if isinstance(data, dict):
        for value in data.values():
            texts.extend(extract_all_text(value))
    elif isinstance(data, list):
        for item in data:
            texts.extend(extract_all_text(item))
    elif isinstance(data, str):
        texts.append(data)
    
    return texts


def llm_self_harm_check(text: str) -> bool:
    """Returns True if the LLM detects self-harm risk."""
    try:
        response = model.chat.completions.create(
            model="gpt-4o-mini",
            max_tokens=5,
            temperature=0,
            messages=[{"role": "user", "content": SAFETY_CLASSIFIER_PROMPT.format(text=text)}]
        )
        result = response.choices[0].message.content.strip().upper()
        return result == "YES"
    except Exception as e:
        # Fail-safe: If classifier fails, assume SAFE to avoid blocking normal responses
        print("Safety classifier error:", e)
        return False


# --------------------------
# SAFETY OVERRIDE PROMPT
# --------------------------

def build_safety_prompt(username: str):
    """Special safety response prompt triggered for suicidal intent messages."""

    return f"""
You are a supportive, non-judgmental emotional support bot.

A user has expressed thoughts of suicide or wanting to harm themselves.

RESPOND WITH:
- 1-4 gentle, SHORT sentences.
- Validate their feelings with warmth.
- Encourage reaching out to someone they trust or a crisis helpline.
- No instructions, no steps, no solutions.
- No jokes, no metaphors, no tough love.
- No clinical language.
- MUST mention {username}.
- Use MAX 1 soft emoji (💜, 🕊️).

Example responses:
- "I'm really glad you reached out, {username}. What you're feeling matters, and talking to someone you trust or a crisis counselor could help 💜"
- "{username}, I hear you, and you don't have to go through this alone. Please reach out to someone close or call a crisis line 🕊️"

Write a safe, compassionate response.

Final Output:
"""


# --------------------------
# NORMAL BOT RESPONSE PROMPT
# --------------------------

def build_normal_prompt(bot_persona, event_type, event_data, context, engagement_context=None):

    username = event_data.get("username", "@User")
    event_rule = EVENT_GUIDELINES.get(
        event_type, 
        "Respond appropriately to this event with emotional sensitivity."
    )

    # SPECIAL HANDLING FOR USER_TAGGED_BOT
    user_message_section = ""
    if event_type == "USER_TAGGED_BOT":
        user_question = event_data.get("question", event_data.get("message", ""))
        if user_question:
            user_message_section = f"""
USER'S MESSAGE TO YOU:
"{user_question}"

YOU MUST:
- Directly respond to what {username} said above
- Address their specific situation/question
- Stay in character with your persona
- Be conversational like responding to a friend
"""

    STRICT_RULES = f"""
STRICT NON-NEGOTIABLE RULES:
- Response MUST be 1-4 sentences ONLY.
- MUST be under 280 characters.
- MUST mention {username}.
- Never start with username in sentence.
- Use MAX 1 emoji.
- NO bullet points or formatting.
- Sara / Blue / Yellow / White may NOT give steps.
- Joe may give small steps ONLY for: STREAK_MILESTONE, PROGRESS_MILESTONE_COMPLETED, DAILY_CHECK_IN.
- Red must be direct but NEVER cruel.
- Emotional events override personality (tone must soften).
"""

    # Phase 4: Add relationship emphasis when detected
    relationship_section = ""
    if event_data.get("relationship_context"):
        relationship_section = """
RELATIONSHIP EMPHASIS (ACTIVATED):
This message is about a relationship. You MUST:
- Focus on attachment patterns, communication dynamics, and boundaries
- Ask about what they need vs what they're tolerating
- Frame everything through relational dynamics, not general advice
- Explore the space between what they want and what they're getting
- Help them see patterns in how they connect with others
"""

    # Phase 5: Add engagement loop instructions
    engagement_section = get_engagement_prompt(engagement_context) if engagement_context else ""

    return f"""
{bot_persona}

EVENT TYPE: {event_type}
EVENT GOAL: {event_rule}

USERNAME: {username}

{user_message_section}
{relationship_section}
{engagement_section}

CONTEXT:
Recent Messages: {context.get("recent_messages", [])}
Current User: {context.get("current_user", {})}
Tribe Mood: {context.get("tribe_mood", {})}

{STRICT_RULES}

Write ONE short response following all rules.

Final Output:
"""


# --------------------------
# REQUEST MODEL
# --------------------------

class BotEvent(BaseModel):
    bot_name: str
    event_type: str
    event_data: dict
    context: dict = {}
    engagement_context: dict = None
    timestamp: Optional[str] = None


# --------------------------
# MAIN ENDPOINT
# --------------------------

@app.get("/")
async def root():
    return FileResponse("index.html")




@app.post("/api/v1/bot-event")
async def bot_event_handler(payload: BotEvent):

    bot_name = payload.bot_name.lower()

    if bot_name not in BOT_PERSONAS:
        return {"success": False, "error": "Invalid bot_name"}

    persona = BOT_PERSONAS[bot_name]

    # ---------------------
    # 1. EXTRACT ALL TEXT FOR SAFETY CHECK
    # ---------------------
    all_texts = []
    all_texts.extend(extract_all_text(payload.event_data))
    all_texts.extend(extract_all_text(payload.context))
    
    combined_text = " ".join(all_texts)
    
    print(f"🔍 Safety check text: {combined_text[:200]}...")

    # ---------------------
    # 2. SAFETY CHECK
    # ---------------------
    if llm_self_harm_check(combined_text):
        print("⚠️ SAFETY OVERRIDE TRIGGERED - Self-harm detected")
        prompt = build_safety_prompt(payload.event_data.get("username", "@User"))
    else:
        # ---------------------
        # 3. NORMAL MODE
        # ---------------------
        prompt = build_normal_prompt(
            bot_persona=persona,
            event_type=payload.event_type,
            event_data=payload.event_data,
            context=payload.context,
            engagement_context=payload.engagement_context
        )

        print(f"Prompt DEBUGGING:\n{prompt}\n")

    # ---------------------
    # 4. GENERATE BOT RESPONSE
    # ---------------------
    response = model.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=120,
        temperature=0.7
    )

    final_text = response.choices[0].message.content.strip()

    return {
        "success": True,
        "response": final_text,
        "safety_triggered": llm_self_harm_check(combined_text)
    }





# --------------------------
# HEALTH CHECK
# --------------------------

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "stumble-bot-api"}