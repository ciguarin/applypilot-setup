"""Prompt builder for the autonomous job application agent."""

import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

from applypilot import config

logger = logging.getLogger(__name__)


def _build_profile_summary(profile: dict) -> str:
    p = profile
    personal = p["personal"]
    work_auth = p["work_authorization"]
    comp = p["compensation"]
    exp = p.get("experience", {})
    avail = p.get("availability", {})
    eeo = p.get("eeo_voluntary", {})

    lines = [
        f"Name: {personal['full_name']}",
        f"Email: {personal['email']}",
        f"Phone: {personal['phone']}",
    ]

    addr_parts = [
        personal.get("address", ""),
        personal.get("city", ""),
        personal.get("province_state", ""),
        personal.get("country", ""),
        personal.get("postal_code", ""),
    ]
    lines.append(f"Address: {', '.join(p for p in addr_parts if p)}")

    if personal.get("linkedin_url"):
        lines.append(f"LinkedIn: {personal['linkedin_url']}")
    if personal.get("github_url"):
        lines.append(f"GitHub: {personal['github_url']}")
    if personal.get("portfolio_url"):
        lines.append(f"Portfolio: {personal['portfolio_url']}")
    if personal.get("website_url"):
        lines.append(f"Website: {personal['website_url']}")

    lines.append(f"Work Auth: {work_auth.get('legally_authorized_to_work', 'See profile')}")
    lines.append(f"Sponsorship Needed: {work_auth.get('require_sponsorship', 'See profile')}")
    if work_auth.get("work_permit_type"):
        lines.append(f"Work Permit: {work_auth['work_permit_type']}")

    currency = comp.get("salary_currency", "USD")
    lines.append(f"Salary Expectation: ${comp['salary_expectation']} {currency}")

    if exp.get("years_of_experience_total"):
        lines.append(f"Years Experience: {exp['years_of_experience_total']}")
    if exp.get("education_level"):
        lines.append(f"Education: {exp['education_level']}")

    lines.append(f"Available: {avail.get('earliest_start_date', 'Immediately')}")
    lines.extend([
        "Age 18+: Yes", "Background Check: Yes", "Felony: No",
        "Previously Worked Here: No", "How Heard: Online Job Board",
    ])

    lines.append(f"Gender: {eeo.get('gender', 'Decline to self-identify')}")
    lines.append(f"Race: {eeo.get('race_ethnicity', 'Decline to self-identify')}")
    lines.append(f"Veteran: {eeo.get('veteran_status', 'I am not a protected veteran')}")
    lines.append(f"Disability: {eeo.get('disability_status', 'I do not wish to answer')}")

    return "\n".join(lines)


def _build_location_check(profile: dict, search_config: dict) -> str:
    personal = profile["personal"]
    location_cfg = search_config.get("location", {})
    accept_patterns = location_cfg.get("accept_patterns", [])
    primary_city = personal.get("city", location_cfg.get("primary", "your city"))

    if accept_patterns:
        city_list = ", ".join(accept_patterns)
    else:
        city_list = primary_city

    return f"""== LOCATION CHECK (do this FIRST before any form) ==
Read the job page. Determine the work arrangement. Then decide:
- "Remote" or "work from anywhere" -> ELIGIBLE. Apply.
- "Hybrid" or "onsite" in {city_list} -> ELIGIBLE. Apply.
- "Hybrid" or "onsite" in another city BUT the posting also says "remote OK" or "remote option available" -> ELIGIBLE. Apply.
- "Onsite only" or "hybrid only" in any city outside the list above with NO remote option -> NOT ELIGIBLE. Stop immediately. Output RESULT:FAILED:not_eligible_location
- City is overseas (India, Philippines, Europe, etc.) with no remote option -> NOT ELIGIBLE. Output RESULT:FAILED:not_eligible_location
- Cannot determine location -> Continue applying. If a screening question reveals it's non-local onsite, answer honestly and let the system reject if needed.
Do NOT fill out forms for jobs that are clearly onsite in a non-acceptable location. Check EARLY, save time."""


def _build_salary_section(profile: dict) -> str:
    comp = profile["compensation"]
    currency = comp.get("salary_currency", "USD")
    floor = comp["salary_expectation"]
    range_min = comp.get("salary_range_min", floor)
    range_max = comp.get("salary_range_max", str(int(floor) + 20000) if floor.isdigit() else floor)
    conversion_note = comp.get("currency_conversion_note", "")

    try:
        floor_int = int(floor)
        examples = [
            (f"${floor_int // 1000}K", floor_int // 2080),
            (f"${(floor_int + 25000) // 1000}K", (floor_int + 25000) // 2080),
            (f"${(floor_int + 55000) // 1000}K", (floor_int + 55000) // 2080),
        ]
        hourly_line = ", ".join(f"{sal} = ${hr}/hr" for sal, hr in examples)
    except (ValueError, TypeError):
        hourly_line = "Divide annual salary by 2080"

    if conversion_note:
        convert_line = f"Posting is in a different currency? -> {conversion_note}"
    else:
        convert_line = "Posting is in a different currency? -> Target midpoint of their range. Convert if needed."

    return f"""== SALARY (think, don't just copy) ==
${floor} {currency} is the FLOOR. Never go below it.
1. Job posting shows a range? -> Answer with the MIDPOINT.
2. Senior/Staff/Lead/Principal/Architect/level II+? -> Min $110K {currency} or posted midpoint if higher.
3. {convert_line}
4. No salary info? -> Use ${floor} {currency}.
5. Asked for a range? -> Midpoint ±10%. No posted range? -> "${range_min}-${range_max} {currency}".
6. Hourly rate? -> Annual ÷ 2080. ({hourly_line})"""


def _build_screening_section(profile: dict) -> str:
    personal = profile["personal"]
    exp = profile.get("experience", {})
    city = personal.get("city", "their city")
    years = exp.get("years_of_experience_total", "multiple")
    target_role = exp.get("target_role", personal.get("current_job_title", "software engineer"))
    work_auth = profile["work_authorization"]

    return f"""== SCREENING QUESTIONS ==
Hard facts -> answer truthfully: location ({city}, no relocation), work auth ({work_auth.get('legally_authorized_to_work', 'see profile')}), citizenship, clearance, criminal/background.
Skills -> be confident. {target_role} with {years} years experience. Same-domain tool = YES.
Open-ended -> 2-3 sentences specific to THIS job. Reference something from the JD + a resume achievement. No generic fluff.
EEO -> "Decline to self-identify" for everything."""


def _build_hard_rules(profile: dict) -> str:
    personal = profile["personal"]
    work_auth = profile["work_authorization"]

    full_name = personal["full_name"]
    preferred_name = personal.get("preferred_name", full_name.split()[0])
    preferred_last = full_name.split()[-1] if " " in full_name else ""
    display_name = f"{preferred_name} {preferred_last}".strip() if preferred_last else preferred_name

    work_auth_rule = "Work auth: Answer truthfully from profile."
    permit_type = work_auth.get("work_permit_type", "")
    sponsorship = work_auth.get("require_sponsorship", "")
    if permit_type:
        work_auth_rule = f"Work auth: {permit_type}. Sponsorship needed: {sponsorship}."

    name_rule = f'Name: Legal name = {full_name}.'
    if preferred_name and preferred_name != full_name.split()[0]:
        name_rule += f' Preferred = {preferred_name}. Use "{display_name}" unless field says "legal name".'

    return f"""== HARD RULES ==
1. Never lie about: citizenship, work auth, criminal history, education, clearance, licenses.
2. {work_auth_rule}
3. {name_rule}"""


def _build_captcha_section() -> str:
    config.load_env()
    capsolver_key = os.environ.get("CAPSOLVER_API_KEY", "")

    return f"""== CAPTCHA ==
CapSolver key: {capsolver_key or 'NOT SET — use MANUAL FALLBACK for all CAPTCHAs'}
Flow: DETECT → SOLVE via API (createTask → poll → inject) → only MANUAL FALLBACK if errorId > 0.
CapSolver is server-side — it does NOT need to see images. Always try API first regardless of CAPTCHA appearance.

--- DETECT (run after every navigation/click/when stuck) ---
Check hCaptcha BEFORE reCAPTCHA (both use data-sitekey).
browser_evaluate: () => {{{{
  const r = {{}};
  const url = window.location.href;
  const hc = document.querySelector('.h-captcha,[data-hcaptcha-sitekey]');
  if (hc) {{ r.type='hcaptcha'; r.sitekey=hc.dataset.sitekey||hc.dataset.hcaptchaSitekey; }}
  if (!r.type && document.querySelector('script[src*="hcaptcha.com"],iframe[src*="hcaptcha.com"]')) {{
    const el=document.querySelector('[data-sitekey]'); if (el) {{ r.type='hcaptcha'; r.sitekey=el.dataset.sitekey; }}
  }}
  if (!r.type) {{ const cf=document.querySelector('.cf-turnstile,[data-turnstile-sitekey]');
    if (cf) {{ r.type='turnstile'; r.sitekey=cf.dataset.sitekey||cf.dataset.turnstileSitekey;
      if (cf.dataset.action) r.action=cf.dataset.action; if (cf.dataset.cdata) r.cdata=cf.dataset.cdata; }}
  }}
  if (!r.type && document.querySelector('script[src*="challenges.cloudflare.com"]'))
    {{ r.type='turnstile_script_only'; r.note='Wait 3s and re-detect.'; }}
  if (!r.type) {{ const s=document.querySelector('script[src*="recaptcha"][src*="render="]');
    if (s) {{ const m=s.src.match(/render=([^&]+)/); if (m&&m[1]!=='explicit') {{ r.type='recaptchav3'; r.sitekey=m[1]; }} }}
  }}
  if (!r.type) {{ const rc=document.querySelector('.g-recaptcha');
    if (rc) {{ r.type='recaptchav2'; r.sitekey=rc.dataset.sitekey; }}
  }}
  if (!r.type && document.querySelector('script[src*="recaptcha"]')) {{
    const el=document.querySelector('[data-sitekey]'); if (el) {{ r.type='recaptchav2'; r.sitekey=el.dataset.sitekey; }}
  }}
  if (!r.type) {{ const fc=document.querySelector('#FunCaptcha,[data-pkey],.funcaptcha');
    if (fc) {{ r.type='funcaptcha'; r.sitekey=fc.dataset.pkey; }}
  }}
  if (r.type) {{ r.url=url; return r; }}
  return null;
}}}}
null=no CAPTCHA. turnstile_script_only=wait 3s re-detect. Any other type=proceed to SOLVE.

--- SOLVE ---
TASK_TYPE: hcaptcha→HCaptchaTaskProxyLess, recaptchav2→ReCaptchaV2TaskProxyLess, recaptchav3→ReCaptchaV3TaskProxyLess, turnstile→AntiTurnstileTaskProxyLess, funcaptcha→FunCaptchaTaskProxyLess

STEP 1 — CREATE TASK:
browser_evaluate: async () => {{{{
  const r=await fetch('https://api.capsolver.com/createTask',{{method:'POST',headers:{{{{'Content-Type':'application/json'}}}},
    body:JSON.stringify({{clientKey:'{capsolver_key}',task:{{type:'TASK_TYPE',websiteURL:'PAGE_URL',websiteKey:'SITE_KEY'}}}})
  }}); return await r.json();
}}}}
recaptchav3: add "pageAction":"submit". turnstile: add "metadata":{{"action":"...","cdata":"..."}} if found.
errorId>0 → MANUAL FALLBACK.

STEP 2 — POLL (every 3s, max 10x):
browser_evaluate: async () => {{{{
  const r=await fetch('https://api.capsolver.com/getTaskResult',{{method:'POST',headers:{{{{'Content-Type':'application/json'}}}},
    body:JSON.stringify({{clientKey:'{capsolver_key}',taskId:'TASK_ID'}})
  }}); return await r.json();
}}}}
processing→wait 3s poll again. ready→extract: reCAPTCHA/hCaptcha=solution.gRecaptchaResponse, Turnstile=solution.token. errorId>0 or 30s→MANUAL FALLBACK.

STEP 3 — INJECT:
reCAPTCHA v2/v3:
browser_evaluate: () => {{{{
  const token='THE_TOKEN';
  document.querySelectorAll('[name="g-recaptcha-response"]').forEach(el=>{{el.value=token;el.style.display='block';}});
  if (window.___grecaptcha_cfg) {{ const c=window.___grecaptcha_cfg.clients;
    for (const k in c) {{ const w=(o,d)=>{{if(d>4||!o)return;for(const x in o){{if(typeof o[x]==='function'&&x.length<3)try{{o[x](token);}}catch(e){{}}else if(typeof o[x]==='object')w(o[x],d+1);}}}};w(c[k],0); }}
  }}
  return 'injected';
}}}}
hCaptcha:
browser_evaluate: () => {{{{
  const token='THE_TOKEN';
  const ta=document.querySelector('[name="h-captcha-response"],textarea[name*="hcaptcha"]'); if(ta)ta.value=token;
  document.querySelectorAll('iframe[data-hcaptcha-response]').forEach(f=>f.setAttribute('data-hcaptcha-response',token));
  return 'injected';
}}}}
Turnstile:
browser_evaluate: () => {{{{
  const token='THE_TOKEN';
  const inp=document.querySelector('[name="cf-turnstile-response"],input[name*="turnstile"]'); if(inp)inp.value=token;
  return 'injected';
}}}}
FunCaptcha:
browser_evaluate: () => {{{{
  const token='THE_TOKEN';
  const inp=document.querySelector('#FunCaptcha-Token,input[name="fc-token"]'); if(inp)inp.value=token;
  return 'injected';
}}}}
After inject: wait 2s, snapshot. Widget gone=success. No change=click Submit. Still stuck=token expired, re-run STEP 1.

--- MANUAL FALLBACK (only if CapSolver errorId > 0) ---
Audio challenge: look for audio/accessibility button. Text/logic puzzles: solve yourself. All else: RESULT:CAPTCHA."""


def build_prompt(job: dict, tailored_resume: str,
                 cover_letter: str | None = None,
                 dry_run: bool = False) -> str:
    profile = config.load_profile()
    search_config = config.load_search_config()
    personal = profile["personal"]

    resume_path = job.get("tailored_resume_path")
    if not resume_path:
        raise ValueError(f"No tailored resume for job: {job.get('title', 'unknown')}")

    src_pdf = Path(resume_path).with_suffix(".pdf").resolve()
    if not src_pdf.exists():
        raise ValueError(f"Resume PDF not found: {src_pdf}")

    full_name = personal["full_name"]
    name_slug = full_name.replace(" ", "_")
    dest_dir = config.APPLY_WORKER_DIR / "current"
    dest_dir.mkdir(parents=True, exist_ok=True)
    upload_pdf = dest_dir / f"{name_slug}_Resume.pdf"
    shutil.copy(str(src_pdf), str(upload_pdf))
    pdf_path = str(upload_pdf)

    cover_letter_text = cover_letter or ""
    cl_upload_path = ""
    cl_path = job.get("cover_letter_path")
    if cl_path and Path(cl_path).exists():
        cl_src = Path(cl_path)
        cl_txt = cl_src.with_suffix(".txt")
        if cl_txt.exists():
            cover_letter_text = cl_txt.read_text(encoding="utf-8")
        elif cl_src.suffix == ".txt":
            cover_letter_text = cl_src.read_text(encoding="utf-8")
        cl_pdf_src = cl_src.with_suffix(".pdf")
        if cl_pdf_src.exists():
            cl_upload = dest_dir / f"{name_slug}_Cover_Letter.pdf"
            shutil.copy(str(cl_pdf_src), str(cl_upload))
            cl_upload_path = str(cl_upload)

    profile_summary = _build_profile_summary(profile)
    location_check = _build_location_check(profile, search_config)
    salary_section = _build_salary_section(profile)
    screening_section = _build_screening_section(profile)
    hard_rules = _build_hard_rules(profile)
    captcha_section = _build_captcha_section()

    city = personal.get("city", "the area")
    if not cover_letter_text:
        cl_display = (
            f"None available. Skip if optional. If required: 2 sentences — "
            f"(1) relevant experience matching this role, (2) available immediately, based in {city}."
        )
    else:
        cl_display = cover_letter_text

    phone_digits = "".join(c for c in personal.get("phone", "") if c.isdigit())

    from applypilot.config import load_blocked_sso
    blocked_sso = load_blocked_sso()

    preferred_name = personal.get("preferred_name", full_name.split()[0])
    last_name = full_name.split()[-1] if " " in full_name else ""
    display_name = f"{preferred_name} {last_name}".strip()

    if dry_run:
        submit_instruction = "Do NOT click Submit. Review all fields, then output RESULT:APPLIED (dry run)."
    else:
        submit_instruction = "Before Submit: snapshot and verify EVERY field matches profile and resume — name, email, phone, location, work auth, resume uploaded. Fix anything wrong FIRST."

    prompt = f"""You are an autonomous job application agent. Submit this application.

== JOB ==
URL: {job.get('application_url') or job['url']}
Title: {job['title']}
Company: {job.get('site', 'Unknown')}
Fit Score: {job.get('fit_score', 'N/A')}/10

== FILES ==
Resume PDF: {pdf_path}
Cover Letter PDF: {cl_upload_path or 'N/A'}

== RESUME TEXT ==
{tailored_resume}

== COVER LETTER ==
{cl_display}

== APPLICANT PROFILE ==
{profile_summary}

{hard_rules}

== NEVER DO (output RESULT:FAILED immediately) ==
- Camera/mic/screen/location permissions requested -> RESULT:FAILED:unsafe_permissions
- Video/audio verification, selfie, ID photo, biometrics -> RESULT:FAILED:unsafe_verification
- Freelancing platform (Mercor, Toptal, Upwork, Fiverr, Turing) -> RESULT:FAILED:not_a_job_application
- Hourly/contract/rate-setting flows (full-time salaried only)
- SSO login (Google/Microsoft OAuth) -> RESULT:FAILED:sso_required
- Payment info, bank details, SSN/SIN

{location_check}

{salary_section}

{screening_section}

== STEPS ==
1. browser_navigate to job URL.
2. browser_snapshot. Run CAPTCHA DETECT. Solve if found.
3. LOCATION CHECK. Not eligible -> RESULT:FAILED:not_eligible_location and stop.
4. Click Apply. If email-only: send_email subject "Application for {job['title']} — {display_name}", body=2-3 sentence pitch + contact, attach "{pdf_path}". Output RESULT:APPLIED.
   After clicking Apply: run CAPTCHA DETECT.
5. Login wall?
   5a. URL is {', '.join(blocked_sso)} or any SSO/OAuth -> RESULT:FAILED:sso_required.
   5b. New tab/popup (browser_tabs list)? Switch to it. SSO URL -> RESULT:FAILED:sso_required.
   5c. Regular login: {personal['email']} / {personal.get('password', '')}
   5d. After Login click: run CAPTCHA DETECT.
   5e. Login failed? Try sign up with same email and password.
   5f. Email required? Wait 8s then search_emails for mail from the site's domain.
       - OTP/code field visible: extract the numeric code, type it into the field.
       - Verification link (no code field): get the link from the email, browser_navigate to it, continue.
       - Password reset email: get reset link, navigate to it, set password to {personal.get('password', '')}, return to login, retry 5c.
       - No email after 20s (search twice with 10s gap): RESULT:FAILED:login_issue
   5g. Switch back to application tab if needed.
   5h. All failed -> RESULT:FAILED:login_issue.
6. Upload resume: delete existing first, browser_file_upload with PDF path. Always upload fresh.
7. Cover letter field? Text -> paste. File -> upload PDF.
8. Check ALL pre-filled fields. ATS parsers are wrong. Fix "Current Job Title" and everything else against profile.
9. Answer screening questions per rules above.
10. {submit_instruction}
11. After submit: CAPTCHA DETECT. Check for new tabs. Snapshot to confirm "thank you" / "application received".
12. Output RESULT.

== RESULT CODES ==
RESULT:APPLIED | RESULT:EXPIRED | RESULT:CAPTCHA | RESULT:LOGIN_ISSUE
RESULT:FAILED:not_eligible_location | RESULT:FAILED:not_eligible_work_auth | RESULT:FAILED:reason

== BROWSER EFFICIENCY ==
- browser_snapshot once per page for element refs. browser_take_screenshot to check results (10x less data).
- Snapshot again only when you need new refs.
- Fill ALL fields in ONE browser_fill_form call.
- Multi-page forms (Workday, Taleo, iCIMS): snapshot each page, fill all, click Next. Repeat to final review.
- After any navigation/Apply/Submit/Login click or when stuck: run CAPTCHA DETECT. Invisible CAPTCHAs (Turnstile, reCAPTCHA v3) block silently with no visual widget.

== FORM TRICKS ==
- New tab opened? browser_tabs list/select. Always check after login/apply/sign-in clicks.
- Workday/Lever pre-fill page: click upload area, browser_file_upload, wait for parse, click Next.
- Dropdown won't fill? Click to open, click the option.
- Checkbox won't check? browser_click it directly.
- Phone with country prefix: type digits only: {phone_digits}
- Date fields: {datetime.now().strftime('%m/%d/%Y')}
- Validation errors? Take snapshot AND screenshot. Fix all, retry.

{captcha_section}

== GIVE UP WHEN ==
- Same page after 3 attempts -> RESULT:FAILED:stuck
- Job closed/expired -> RESULT:EXPIRED
- Page broken/500 -> RESULT:FAILED:page_error"""

    return prompt
