"""OpenAI claim-extraction + verification for io6 (cosmetic-ad fact-check).

The bundled local path (Phi-3 / regex + a small KB) is unreliable on CPU and tends to extract
no claims at all → "trust 100%". When an OpenAI key is configured we instead send the ad's
spoken transcript + on-screen text (+ detected objects) to a text model (GPT-4o by default)
and ask it to list the marketing claims and assess each against the EU common criteria for
cosmetic claims (Reg. (EU) No 655/2013).

Reuses io1's key loader (OPENAI_API_KEY env, else backend/data/openai_key.txt).
Env: IO6_OPENAI_MODEL (default IO1_OPENAI_MODEL or "gpt-4o"), IO6_OPENAI_TIMEOUT.
"""
from __future__ import annotations

import json
import os
import re

try:
    from backend.modules.io1_ai_generated.openai_vision import api_key as _io1_api_key
except Exception:  # pragma: no cover
    _io1_api_key = None

_MODEL = (os.environ.get("IO6_OPENAI_MODEL") or os.environ.get("IO1_OPENAI_MODEL") or "gpt-4o").strip() or "gpt-4o"
_TIMEOUT = float(os.environ.get("IO6_OPENAI_TIMEOUT", os.environ.get("IO1_OPENAI_TIMEOUT", "60")))
_API_URL = "https://api.openai.com/v1/chat/completions"


def api_key():
    k = (os.environ.get("OPENAI_API_KEY") or "").strip()
    if k:
        return k
    if _io1_api_key is not None:
        try:
            return _io1_api_key()
        except Exception:
            return None
    return None


def available() -> bool:
    return bool(api_key())


def model_name() -> str:
    return _MODEL


_SYSTEM = (
    "You are a compliance analyst for cosmetic advertising in the European Union. You receive the spoken "
    "transcript and the on-screen text of one cosmetics advertisement. Identify the MARKETING CLAIMS it makes "
    "(about ingredients, effects, results, percentages, ratings, endorsements, 'before/after', guarantees…) "
    "and assess each against the EU common criteria for cosmetic claims — Regulation (EU) No 655/2013: a claim "
    "must be (1) legally compliant — it may NOT imply a medicinal / therapeutic effect; (2) truthful; "
    "(3) supported by adequate and verifiable evidence; (4) honest — it must not overstate what the product does; "
    "(5) fair — no denigration of competitors; (6) it must allow the consumer to make an informed decision.\n"
    "Treat unsupported ABSOLUTES as FALSE / non-compliant unless the ad explicitly states a credible basis: "
    "'100% effective', 'guaranteed results', 'eliminates / erases wrinkles', 'cures …', 'instantly', 'permanent', "
    "'#1 / number-one dermatologist recommended', 'clinically proven' with no study cited, 'no chemicals'.\n"
    "Be fair the other way too: ordinary hedged, sensorial or descriptive claims — 'helps hydrate', 'leaves skin "
    "feeling soft', 'with shea butter', 'dermatologically tested', 'reduces the appearance of fine lines' — are "
    "normally TRUE / compliant. An ad with no problematic claim is RELIABLE.\n"
    "Answer with ONLY a JSON object (no markdown, no prose around it) with EXACTLY these keys:\n"
    '  "claims": array of objects — each {"claim": short quote or paraphrase (string), "verdict": "TRUE" or "FALSE", '
    '"confidence": number 0.5-0.99, "severity": "info" | "warning" | "critical", "reason": ONE short ENGLISH sentence, '
    '"eu_articles": array of short refs e.g. ["Reg. 655/2013 — honesty", "Reg. 655/2013 — evidential support"]}\n'
    '  "global_verdict": "RELIABLE" or "MISLEADING"\n'
    '  "trust_score": integer 0-100 — overall reliability of the ad\n'
    '  "summary": 1-2 short ENGLISH sentences summarising the assessment'
)


def evaluate(transcript: str, ocr_texts, yolo_classes=None) -> dict | None:
    """Returns {claims, trust_score, global_verdict, summary, eu_articles_cited, model} — or None if no key/deps."""
    key = api_key()
    if not key:
        return None
    try:
        import requests  # noqa: F401
    except ImportError:
        return None

    transcript = (transcript or "").strip()
    ocr_lines = [str(t).strip() for t in (ocr_texts or []) if str(t).strip()]
    ocr = "\n".join(ocr_lines)[:1800]
    obj_str = ", ".join(sorted((yolo_classes or {}).keys())) if isinstance(yolo_classes, dict) else ""

    if not transcript and not ocr:
        return {
            "claims": [], "trust_score": 100.0, "global_verdict": "RELIABLE",
            "summary": "No spoken or on-screen marketing claim could be read in this ad — nothing to assess.",
            "eu_articles_cited": [], "model": _MODEL,
        }

    user = (
        f"AD TRANSCRIPT (spoken):\n{transcript[:2800] or '(none)'}\n\n"
        f"ON-SCREEN TEXT:\n{ocr or '(none)'}\n\n"
        f"OBJECTS DETECTED IN FRAMES: {obj_str or '(none)'}\n\n"
        "Extract and assess the marketing claims of this cosmetics ad. Return only the requested JSON."
    )
    payload = {
        "model": _MODEL,
        "temperature": 0,
        "max_tokens": 1200,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user},
        ],
    }
    import requests
    try:
        r = requests.post(
            _API_URL,
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json=payload, timeout=_TIMEOUT,
        )
    except Exception as e:
        raise RuntimeError(f"OpenAI request failed ({type(e).__name__}: {e})") from e
    if r.status_code != 200:
        raise RuntimeError(f"OpenAI API {r.status_code}: {r.text[:300]}")
    try:
        content = r.json()["choices"][0]["message"]["content"]
    except Exception as e:
        raise RuntimeError(f"Unexpected OpenAI response ({type(e).__name__})") from e

    obj = _parse_json(content)
    if not isinstance(obj, dict):
        raise RuntimeError(f"OpenAI did not return usable JSON: {str(content)[:200]}")

    raw = obj.get("claims") or []
    claims = []
    eu_all = set()
    for c in raw:
        if not isinstance(c, dict):
            continue
        v = str(c.get("verdict", "")).strip().upper()
        if v.startswith("FALSE") or v in ("MISLEADING", "NON_COMPLIANT", "NONCOMPLIANT", "FAKE"):
            v = "FALSE"
        elif v.startswith("TRUE") or v in ("COMPLIANT", "OK", "VALID"):
            v = "TRUE"
        else:
            v = "TO_VERIFY"
        try:
            conf = max(0.3, min(0.99, float(c.get("confidence", 0.7))))
        except (TypeError, ValueError):
            conf = 0.7
        sev = str(c.get("severity", "")).strip().lower()
        if sev not in ("info", "warning", "critical"):
            sev = "critical" if v == "FALSE" else "info"
        eus = [str(a).strip() for a in (c.get("eu_articles") or []) if str(a).strip()][:4]
        for a in eus:
            eu_all.add(a)
        reason = str(c.get("reason", "")).strip()
        claims.append({
            "claim": str(c.get("claim", "")).strip()[:300] or "(claim)",
            "verdict": v,
            "confidence": round(conf, 3),
            "severity": sev,
            "evidence": [{"source": f"OpenAI · {_MODEL}", "description": reason or "Assessed against the EU common criteria for cosmetic claims."}],
            "reasons": [reason] if reason else [],
            "eu_articles": eus,
        })

    n_false = sum(1 for c in claims if c["verdict"] == "FALSE")
    gv = str(obj.get("global_verdict", "")).strip().upper()
    if gv not in ("RELIABLE", "MISLEADING"):
        gv = "MISLEADING" if n_false > 0 else "RELIABLE"
    try:
        ts = int(round(float(obj.get("trust_score", 100 if n_false == 0 else 40))))
    except (TypeError, ValueError):
        ts = 100 if n_false == 0 else 40
    ts = max(0, min(100, ts))
    # consistency
    if n_false > 0 and gv == "RELIABLE":
        gv = "MISLEADING"
        ts = min(ts, 49)
    if n_false == 0 and gv == "MISLEADING":
        gv = "RELIABLE"
        ts = max(ts, 60)
    return {
        "claims": claims,
        "trust_score": float(ts),
        "global_verdict": gv,
        "summary": str(obj.get("summary", "")).strip(),
        "eu_articles_cited": sorted(eu_all),
        "model": _MODEL,
    }


def _parse_json(s):
    if not isinstance(s, str):
        return None
    s = s.strip()
    try:
        return json.loads(s)
    except Exception:
        pass
    m = re.search(r"\{.*\}", s, re.S)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return None
