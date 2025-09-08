from .config import settings
from jinja2 import Template
import google.generativeai as genai

# =========================
# Fallback Jinja templates
# (text versions; you can switch to HTML later)
# =========================
INTRO_TMPL = Template("""Hi {{ first_name or 'there' }},

I'm {{ from_name }} — an independent software developer & freelance contractor. I help teams deliver web apps, e-commerce, mobile apps, and AI automation/AI solutions that remove repetitive work and speed up ops.

Portfolio: {{ portfolio_url }}
CV: {{ cv_url }}

If support on {{ company or 'your team' }}’s roadmap ({{ company_focus or 'engineering' }}) is useful, I’d be happy to share a short plan.
""")

FOLLOW1_TMPL = Template("""Hi {{ first_name or 'there' }}, circling back.

I help with web/e-commerce/mobile and AI automation (workflows, agents, data piping). Quick context is in my portfolio: {{ portfolio_url }}
""")

FOLLOW2_TMPL = Template("""Hi {{ first_name or 'there' }}, quick nudge.

Recent win: automated ops to cut manual steps & response times using lightweight AI workflows. If that’s relevant for {{ company or 'your side' }}, I can outline a 3-step approach.

Portfolio: {{ portfolio_url }}
""")

CUTOFF_TMPL = Template("""Hi {{ first_name or 'there' }}, I’ll close the loop here.

If timing shifts later, here are my links:
Portfolio: {{ portfolio_url }} | CV: {{ cv_url }}
""")

# =========================
# Universal footers (text + HTML)
# =========================
FOOTER_TXT = Template("""--
M. Rehman | Software Developer & AI Automation
Portfolio: {{ portfolio_url }} | CV: {{ cv_url }}
""")

FOOTER_HTML = Template("""<hr style="border:none;border-top:1px solid #eee;margin:16px 0;">
<p style="margin:0;font:12px/1.45 -apple-system,BlinkMacSystemFont,Segoe UI,Arial">
  <strong>M. Rehman</strong> &nbsp;|&nbsp; Software Developer & AI Automation<br>
  <a href="{{ portfolio_url }}" target="_blank">Portfolio</a> &nbsp;|&nbsp;
  <a href="{{ cv_url }}" target="_blank">CV</a><br>
</p>""")

def ensure_footer(body: str, ctx: dict) -> str:
    """Append a consistent footer once; supports text or HTML bodies."""
    if not body:
        body = ""
    normalized = body.lower()
    if "unsubscribe:" in normalized or ">unsubscribe<" in normalized:
        # already present
        return body.strip() + ("\n" if not body.lstrip().startswith("<") else "")
    if body.lstrip().startswith("<"):
        return body.rstrip() + FOOTER_HTML.render(**ctx)
    return body.rstrip() + "\n\n" + FOOTER_TXT.render(**ctx) + "\n"

# =========================
# Subjects
# =========================
def build_subject(step: int, company: str | None, from_name: str) -> str:
    if step == 0:
        return f"{from_name} — help with web/mobile/AI for {company}" if company else f"{from_name} — help with web/mobile/AI"
    if step == 1:
        return "Circling back on web/mobile/AI help"
    if step == 2:
        return "Quick nudge on engineering support"
    return "Signing off (leaving links)"

# =========================
# Local (Jinja) renderer
# =========================
def render_body_local(step: int, ctx: dict) -> str:
    if step == 0:
        return ensure_footer(INTRO_TMPL.render(**ctx), ctx)
    if step == 1:
        return ensure_footer(FOLLOW1_TMPL.render(**ctx), ctx)
    if step == 2:
        return ensure_footer(FOLLOW2_TMPL.render(**ctx), ctx)
    return ensure_footer(CUTOFF_TMPL.render(**ctx), ctx)

# =========================
# Gemini (LLM) renderer
# =========================
def render_with_gemini(step: int, ctx: dict) -> str:
    """
    Draft plain-text copy via Gemini for the given step, then enforce footer.
    Persona: Independent Software Developer & Freelance Contractor
    Services: Web apps, E-commerce, Mobile apps, AI Automation, AI Solutions
    """
    import json

    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    llm_ctx = {
        "recipient_first_name": ctx.get("first_name"),
        "recipient_company": ctx.get("company"),
        "recipient_focus": ctx.get("company_focus"),
        "sender_name": ctx.get("from_name"),
        "portfolio_url": ctx.get("portfolio_url"),
        "cv_url": ctx.get("cv_url"),
        "step": step
    }

    prompt = f"""
You are writing a SHORT, PLAIN-TEXT cold email for step={step}.
Sender persona: independent Software Developer & Freelance Contractor delivering:
- Web Apps
- E-commerce builds/integrations
- Mobile App development
- AI Automation (workflows, agents, data pipelines)
- AI Solutions (custom chatbots, RAG, analytics)

Tone: respectful, human, low-friction; open a conversation, not a hard pitch.
Audience: CEOs/CTOs/Managers. Use simple sentences. Avoid hype.

Constraints (must follow):
- 80–130 words.
- Pure plain text (no HTML).
- 1–2 links MAX (prefer portfolio then CV).
- Use first name if provided; else “there”.
- Mention company/focus naturally once if available.
- No spammy phrases or long intros.
- The email should NOT include a signature/footer; that will be appended by the system.

Step guidance:
- step=0 intro: concise intro + how you can help (web/e-com/mobile/AI) + portfolio link.
- step=1 fu1: gentle check-in; add one concrete outcome/stack hint.
- step=2 fu2: brief nudge; tiny case hint (e.g., reduced ops time via automation).
- step=3 cutoff: respectful sign-off; keep links for later.

Context (JSON):
{json.dumps(llm_ctx, ensure_ascii=False)}
"""
    resp = model.generate_content(prompt)
    body = (getattr(resp, "text", "") or "").strip()
    return ensure_footer(body, ctx)

# =========================
# Public API
# =========================
def build_email(step: int, ctx: dict) -> tuple[str, str]:
    """
    Returns (subject, body). Uses Gemini if configured; otherwise Jinja fallback.
    ctx expects: first_name, company, company_focus, email, from_name,
                 portfolio_url, cv_url, unsub_url
    """
    import traceback
    subject = build_subject(step, ctx.get("company"), ctx.get("from_name"))
    if not settings.GEMINI_API_KEY:
        return subject, render_body_local(step, ctx)
    try:
        body = render_with_gemini(step, ctx)
        if not body.strip():
            # safety net
            return subject, render_body_local(step, ctx)
        return subject, body
    except Exception as e:
        print("⚠️ Gemini error:", e)
        traceback.print_exc()
        return subject, render_body_local(step, ctx)
