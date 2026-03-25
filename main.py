from fastapi import FastAPI
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
from persona_config import (
    BOT_PERSONAS,
    EVENT_GUIDELINES,
    POETRY_RULE,
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

    # SPECIAL HANDLING FOR GUIDE_PROMPT (guide-initiated, no target user)
    if event_type == "GUIDE_PROMPT":
        recent_context = event_data.get("recent_context", [])
        context_text = ""
        if recent_context:
            context_lines = [f"- {m.get('username', '?')}: {m.get('message', '')[:80]}" for m in recent_context]
            context_text = f"\nRECENT CONVERSATION (for context only — do NOT reply to these):\n" + "\n".join(context_lines)

        return f"""
{bot_persona}

EVENT TYPE: GUIDE_PROMPT
EVENT GOAL: {event_rule}

TIME OF DAY: {event_data.get('time_of_day', 'afternoon')}
TRIBE: {event_data.get('tribe_name', 'the group')}
{context_text}

RULES:
- You are STARTING a conversation, NOT responding to anyone.
- Do NOT mention any specific user by name.
- Do NOT reference or quote any recent messages directly.
- Keep it 1-3 sentences max. One emoji max.
- Make it feel natural and inviting — like a friend casually dropping a thought.
- End with an open question that anyone can answer.
- Stay in your persona's voice and role.

{POETRY_RULE}

Write ONE short conversation-starting prompt.

Final Output:
"""

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
- MUST mention {username}.
- Never start with username in sentence.
- Use MAX 1 emoji.
- NO bullet points or formatting.
- Sara / Blue / Yellow / White may NOT give steps.
- Joe may give small steps ONLY for: STREAK_MILESTONE, PROGRESS_MILESTONE_COMPLETED, DAILY_CHECK_IN.
- Red must be direct but NEVER cruel.
- Emotional events override personality (tone must soften).
- You are responding to ONLY this one message from {username}. Do NOT reference other users, earlier messages, or summarize the thread. Address this person directly.
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

    # Phase 6: Style instruction (from Django backend)
    style_section = ""
    if event_data.get('style_instruction'):
        style_section = f"""
RESPONSE STYLE:
{event_data['style_instruction']}
You MUST include poetic, symbolic, or mythic language in at least one line of your response.
"""

    # Phase 6: Time of day context
    time_section = ""
    time_of_day = event_data.get('time_of_day', '')
    if time_of_day:
        time_prompts = {
            'morning': 'It is morning. Set a grounding, intentional tone. Help them start their day with presence.',
            'afternoon': 'It is afternoon. Invite reflection. Help them check in with themselves mid-day.',
            'evening': 'It is evening. Encourage integration. Help them process and settle from the day.',
        }
        time_section = f"\nTIME CONTEXT: {time_prompts.get(time_of_day, '')}\n"

    return f"""
{bot_persona}

EVENT TYPE: {event_type}
EVENT GOAL: {event_rule}

USERNAME: {username}

{user_message_section}
{relationship_section}
{engagement_section}
{style_section}
{time_section}

CONTEXT:
Target Message: "{event_data.get('message', '')}" from {username}
Current User: {context.get("current_user", {})}
Tribe Mood: {context.get("tribe_mood", {})}

{STRICT_RULES}

{POETRY_RULE}

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
    engagement_context: Optional[dict] = None
    response_style: Optional[dict] = None
    style_instruction: Optional[str] = None
    time_of_day: Optional[str] = None
    tier: Optional[str] = None
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
    # 0. MERGE NEW FIELDS INTO EVENT_DATA
    # ---------------------
    event_data = payload.event_data.copy()
    if payload.response_style and 'response_style' not in event_data:
        event_data['response_style'] = payload.response_style
    if payload.style_instruction and 'style_instruction' not in event_data:
        event_data['style_instruction'] = payload.style_instruction
    if payload.time_of_day and 'time_of_day' not in event_data:
        event_data['time_of_day'] = payload.time_of_day
    if payload.tier and 'tier' not in event_data:
        event_data['tier'] = payload.tier

    # ---------------------
    # 1. EXTRACT ALL TEXT FOR SAFETY CHECK
    # ---------------------
    all_texts = []
    all_texts.extend(extract_all_text(event_data))
    all_texts.extend(extract_all_text(payload.context))
    
    combined_text = " ".join(all_texts)
    
    print(f"🔍 Safety check text: {combined_text[:200]}...")

    # ---------------------
    # 2. SAFETY CHECK
    # ---------------------
    if llm_self_harm_check(combined_text):
        print("⚠️ SAFETY OVERRIDE TRIGGERED - Self-harm detected")
        prompt = build_safety_prompt(event_data.get("username", "@User"))
    else:
        # ---------------------
        # 3. NORMAL MODE
        # ---------------------
        prompt = build_normal_prompt(
            bot_persona=persona,
            event_type=payload.event_type,
            event_data=event_data,
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