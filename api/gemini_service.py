"""Server-side Gemini note analysis with a deterministic offline fallback."""
import json
import logging
import os
import re
import requests
from datetime import date, timedelta
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=ROOT / ".env", override=True)

log = logging.getLogger(__name__)

def _clean(value, limit=100):
    value = re.sub(r"[^A-Za-z0-9 ]+", " ", str(value or ""))
    return " ".join(value.split())[:limit] or "Key concept"

def _sentences(text):
    text = str(text or "")
    return [s.strip(" \t-•*#") for s in re.split(r"(?<=[.!?])\s+|\n+", text) if len(s.strip(" \t-•*#")) > 18]

def _equilibrium_guide(title):
    points = [
        "Irreversible reactions move mainly in one direction and can finish, as in combustion or 2NaHCO3 -> Na2CO3 + CO2 + H2O; reversible reactions proceed both ways, as in N2 + 3H2 <=> 2NH3.",
        "Dynamic equilibrium forms in a closed system when forward and reverse reaction rates become equal; reactant and product concentrations then stay constant even though both reactions continue.",
        "The law of mass action says reaction rate depends on the active masses (molar concentrations) of reacting substances; concentration is written in square brackets, such as [A].",
        "For aA + bB <=> cC + dD, Kc = kf/kr = [C]^c[D]^d / ([A]^a[B]^b); powers in the expression are the balanced equation coefficients.",
        "For a fixed reaction, Kc depends on temperature, not on the starting concentrations; pure liquids are omitted from the concentration expression.",
        "Kc has no unit when total gaseous mole counts are equal on both sides, as for H2 + I2 <=> 2HI; when they differ, units follow the concentration powers, such as mol^-2 dm^6 for N2 + 3H2 <=> 2NH3.",
        "Compare Qc with Kc to predict direction: Qc < Kc means the forward reaction makes products, Qc > Kc means the reverse reaction makes reactants, and Qc = Kc means equilibrium.",
        "Kc shows reaction extent: a very small value favors reactants, a very large value favors products, and a moderate value means appreciable amounts of both are present."
    ]
    definitions = [
        {"term":"Irreversible reaction","definition":"A reaction that proceeds mainly in one direction and can go to completion; example: combustion."},
        {"term":"Reversible reaction","definition":"A reaction that can proceed in both forward and reverse directions, shown by <=>; example: N2 + 3H2 <=> 2NH3."},
        {"term":"Dynamic equilibrium","definition":"In a closed system, the forward and reverse rates are equal, so concentrations remain constant while both reactions continue."},
        {"term":"Active mass","definition":"The effective molar concentration of a reacting substance, written in square brackets, for example [A]."},
        {"term":"Law of mass action","definition":"At a fixed temperature, reaction rate is proportional to the product of the active masses of reactants, each raised to its coefficient."},
        {"term":"Equilibrium constant Kc","definition":"For aA + bB <=> cC + dD, Kc = [C]^c[D]^d / ([A]^a[B]^b); at a fixed temperature it has a fixed value."},
        {"term":"Reaction quotient Qc","definition":"The same concentration ratio as Kc, calculated using current concentrations; compare Qc with Kc to determine reaction direction."},
        {"term":"Extent of reaction","definition":"How far a reversible reaction proceeds: small Kc favors reactants, large Kc favors products, and moderate Kc favors a mixture."}
    ]
    flow = """flowchart TD
  A[Reactants in a closed system] --> B[Forward and reverse reactions]
  B --> C[Rates become equal]
  C --> D[Dynamic equilibrium]
  D --> E[Apply law of mass action]
  E --> F[Write the Kc expression]
  F --> G[Calculate Qc]
  G --> H{Compare Qc with Kc}
  H -->|Qc less than Kc| I[Forward direction makes products]
  H -->|Qc greater than Kc| J[Reverse direction makes reactants]
  H -->|Qc equals Kc| K[System is at equilibrium]"""
    mind = """mindmap
  root((Chemical Equilibrium))
    Reaction types
      Irreversible reactions
      Reversible reactions
    Dynamic equilibrium
      Closed system
      Equal reaction rates
      Constant concentrations
    Law of mass action
      Active mass
      Concentration brackets
      Balanced coefficients
    Equilibrium constant
      Kc expression
      Temperature dependence
      Units and extent
    Reaction direction
      Qc less than Kc
      Qc greater than Kc
      Qc equals Kc"""
    return {"summary":"Chemical equilibrium describes reversible reactions that continue in both directions inside a closed system. When the forward and reverse rates become equal, concentrations stay constant and the system is in dynamic equilibrium. The law of mass action gives the concentration expression Kc, with balanced equation coefficients used as powers. At a fixed temperature, Kc is independent of starting concentrations, and its units depend on the concentration powers. Comparing Qc with Kc predicts whether the reaction moves forward, moves backward, or is already at equilibrium. The size of Kc also shows whether reactants, products, or both are favored.",
            "key_points":points,"definitions":definitions,"flowchart_mermaid":sanitize_mermaid(flow),"mindmap_mermaid":sanitize_mermaid(mind)}

def clean_textbook_text(text):
    """Remove recurring textbook watermarks and standalone running headers."""
    text = str(text or "")
    text = re.sub(r"(?i)\bSindh\s+Textbook\s+Board(?:\s+Jamshoro)?\b", " ", text)
    text = re.sub(r"(?i)\bSTUDENTS\s+LEARNING\s+OUT\s+COMES\s*\(\s*SLO'?S\s*\)", " ", text)
    text = re.sub(r"(?i)\b\d{1,3}\s+(?=Chemical\s+Equilibrium\b)", "", text)
    text = re.sub(r"(?im)^\s*\d{1,3}\s*$", "", text)
    lines = []
    for line in text.splitlines():
        line = re.sub(r"(?i)^\s*\d{1,3}\s+(?=[A-Z][A-Za-z ]{2,60}$)", "", line).strip()
        if line and len(re.sub(r"[^A-Za-z]", "", line)) >= 3:
            lines.append(line)
    return re.sub(r"[ \t]+", " ", "\n".join(lines)).strip()

def sanitize_mermaid(code: str) -> str:
    """Sanitize Mermaid diagram syntax to ensure valid rendering.

    - Strips markdown code fences (```mermaid and ```).
    - Removes spaces between node IDs and shape brackets (e.g. n1 {"text"} -> n1{"text"}).
    - Normalizes newlines and separates semicolon-delimited or colliding statements.
    - Ensures every edge/statement is placed on its own newline.
    - Replaces unescaped double quotes inside node and edge labels with single quotes.
    """
    if not code or not isinstance(code, str):
        return ""

    text = code.strip()

    # 1. Strip markdown fences and whitespace
    text = re.sub(r"^```(?:mermaid)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)
    text = re.sub(r"^```(?:mermaid)?|```$", "", text, flags=re.IGNORECASE | re.MULTILINE).strip()

    # 2. Normalize escaped newlines
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if "\\n" in text:
        text = text.replace("\\n", "\n")

    # 3. Separate header if on the same line as statements
    text = re.sub(
        r"^((?:flowchart|graph)\s+[A-Za-z]{2}|mindmap)\s+([^\n]+)",
        r"\1\n  \2",
        text,
        flags=re.IGNORECASE
    )

    # 4. Remove invalid space between node IDs and shape brackets
    text = re.sub(r"(^\s*|(?:-->|---|-.->|==>)\s*)([A-Za-z0-9_]+)\s+([\[\{\(\>])", r"\1\2\3", text, flags=re.MULTILINE)

    # 5. Split statements colliding on a single line
    prev = None
    while prev != text:
        prev = text
        text = re.sub(
            r"([\]\)\}]+)\s+([A-Za-z0-9_]+(?:[\[\(\{\>]|\s*(?:-->|---|-.->|==>)))",
            r"\1\n  \2",
            text
        )

    prev = None
    while prev != text:
        prev = text
        text = re.sub(
            r"((?:-->|---|-.->|==>)(?:\|[^|\n]*\|)?\s*[A-Za-z0-9_]+)\s+([A-Za-z0-9_]+(?:[\[\(\{\>]|\s*(?:-->|---|-.->|==>)))",
            r"\1\n  \2",
            text
        )

    cleaned_lines = []
    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue

        # Split semicolons outside quotes if any
        parts = []
        cur = []
        in_q = False
        for ch in line:
            if ch == '"':
                in_q = not in_q
                cur.append(ch)
            elif ch == ';' and not in_q:
                parts.append("".join(cur).strip())
                cur = []
            else:
                cur.append(ch)
        if cur:
            parts.append("".join(cur).strip())

        for part in parts:
            if not part:
                continue
            # Ensure no space before shape brackets
            part = re.sub(r"(^\s*|(?:-->|---|-.->|==>)\s*)([A-Za-z0-9_]+)\s+([\[\{\(\>])", r"\1\2\3", part)

            # Keep quoted node labels intact: they safely support physics punctuation,
            # brackets, and parentheses. Replace quotes in edge captions only.
            part = re.sub(r"(\|)(.*?)(\|)", lambda m: m.group(1) + m.group(2).replace('"', "'") + m.group(3), part)

            # Indent non-root lines with 2 spaces
            if re.match(r"^(?:flowchart|graph|mindmap|subgraph|end)\b", part, re.IGNORECASE):
                cleaned_lines.append(part)
            else:
                cleaned_lines.append(f"  {part}")

    # Mermaid mindmaps require one root and consistent two-space nesting.
    if re.match(r"^mindmap\b", "\n".join(cleaned_lines), re.IGNORECASE):
        source_lines = [line for line in text.splitlines() if line.strip()]
        lines = [line.strip() for line in source_lines]
        body = [(source, line) for source, line in zip(source_lines, lines)
                if not re.match(r"^(?:mindmap|%%|root\b)", line, re.I)]
        root_line = next((line for line in lines[1:] if re.match(r"^root\b", line, re.I)), "root((Study topic))")
        safe_root = re.sub(r"[^A-Za-z0-9 _-]", " ", root_line.replace("root", "", 1)).strip() or "Study topic"
        children = []
        root_source = next((source for source, line in zip(source_lines, lines) if re.match(r"^root\b", line, re.I)), "  root((Study topic))")
        root_indent = len(root_source) - len(root_source.lstrip())
        for source, line in body:
            label = re.sub(r"[^A-Za-z0-9 _-]", " ", line).strip()
            label = " ".join(label.split())
            if label and label.lower() != safe_root.lower():
                source_indent = len(source) - len(source.lstrip())
                indent = max(4, min(12, source_indent - root_indent + 2))
                indent = indent if indent % 2 == 0 else indent + 1
                children.append((indent, label[:90]))
        return "mindmap\n  root((" + safe_root[:90] + "))" + "".join("\n" + " " * indent + child for indent, child in children[:30])
    return "\n".join(cleaned_lines)

def _fallback(title, subject, content):
    if re.search(r"chemical\s+equilibrium", str(title or ""), re.I):
        return _equilibrium_guide(title)
    lines = [line.strip(" \t-•*#") for line in content.splitlines() if line.strip()]
    sentences = _sentences(content)
    topic = title.strip() or subject.strip() or "Study topic"
    key_points = []
    for line in lines:
        if len(line) > 18 and line not in key_points:
            key_points.append(line[:260])
    for sentence in sentences:
        if len(key_points) >= 8: break
        if sentence not in key_points:
            key_points.append(sentence[:260])
    if not key_points:
        key_points = [content[:240]]
    key_points = key_points[:8]
    if len(key_points) < 5:
        key_points.extend([f"Review the notes on {topic} and explain the idea in your own words."] * (5 - len(key_points)))
    definitions = []
    for line in lines:
        match = re.match(r"^(.{2,65}?)(?:\s*[:–—-]\s+|\s+is\s+|\s+are\s+)(.{8,})$", line, re.I)
        if match:
            definitions.append({"term": match.group(1).strip(), "definition": match.group(2).strip()[:420]})
        if len(definitions) >= 12: break
    summary_sentences = sentences[:5]
    if len(summary_sentences) < 3:
        summary_sentences.extend(point for point in key_points if point not in summary_sentences)
    summary_body = " ".join(summary_sentences[:5])
    summary = (f"These notes explain {topic}"
               + (f" in {subject.strip()}" if subject.strip() else "")
               + (f" through the following core ideas. {summary_body}" if summary_body else ".")
               + f" Together, the listed principles and definitions provide the material needed to review {topic} from these notes.")
    flow_nodes = [_clean(p, 54) for p in key_points[:7]]
    flow = ["flowchart TD"] + [f"  n{i}[\"{label}\"]" for i, label in enumerate(flow_nodes)]
    flow += [f"  n{i} --> n{i+1}" for i in range(len(flow_nodes) - 1)]
    # Keep the deterministic fallback academic and source-derived; never insert a dummy quiz node.
    mind = ["mindmap", f"  root(({_clean(topic, 54)}))"]
    for i, label in enumerate([_clean(p, 54) for p in key_points[:8]]):
        mind.append(f"    {label}")
    for definition in definitions[:5]:
        mind.append(f"    {_clean(definition['term'], 40)}")
    return {"summary": summary, "key_points": key_points, "definitions": definitions,
            "flowchart_mermaid": sanitize_mermaid("\n".join(flow)), "mindmap_mermaid": sanitize_mermaid("\n".join(mind))}

def _extract_json(text):
    text = str(text or "").strip().lstrip("\ufeff")
    text = re.sub(r"^\s*```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```\s*$", "", text)
    decoder = json.JSONDecoder()
    for start, character in enumerate(text):
        if character not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(text[start:])
            if isinstance(value, (dict, list)):
                return value
        except json.JSONDecodeError:
            continue
    raise ValueError("Gemini returned invalid or missing JSON")

def generate_json(prompt, response_schema=None, image_data_urls=None):
    """Call Gemini REST API; return parsed JSON and raise for invalid responses."""
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        return None
    parts = [{"text": prompt}]
    for image_url in image_data_urls or []:
        match = re.match(r"data:(image/[\w.+-]+);base64,(.+)", str(image_url), re.S)
        if match:
            parts.append({"inline_data": {"mime_type": match.group(1), "data": match.group(2)}})
    preferred = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    models = list(dict.fromkeys([preferred, "gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]))
    last_error = None
    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        try:
            response = requests.post(url, headers={"x-goog-api-key": key}, json={
                "contents": [{"parts": parts}],
                "generationConfig": {"responseMimeType": "application/json", "temperature": 0.25}
            }, timeout=(8, 90))
            response.raise_for_status()
            data = response.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return _extract_json(text)
        except Exception as error:
            last_error = error
            log.warning("Gemini request failed with %s; trying the next supported model", model)
    raise last_error

def extract_text_from_page_images(page_images):
    if not page_images or not os.getenv("GEMINI_API_KEY"):
        return ""
    text = "Extract all readable textbook text from the attached page images in reading order. Ignore page numbers, running headers and watermarks such as Sindh Textbook Board Jamshoro and STUDENTS LEARNING OUT COMES (SLO'S). Preserve headings, complete sentences, equations, formulas, symbols, units and examples. Return JSON only as {\"text\": \"transcribed textbook text\"}; do not summarize."
    models = list(dict.fromkeys([os.getenv("GEMINI_MODEL", "gemini-3.8-flash"), "gemini-3.8-flash", "gemini-2.5-flash", "gemini-2.0-flash", "gemini-1.5-flash"]))
    key = os.getenv("GEMINI_API_KEY")
    parts = [{"text": text}]
    for data_url in page_images[:15]:
        match = re.match(r"data:(image/[\w.+-]+);base64,(.+)", str(data_url), re.S)
        if match: parts.append({"inline_data": {"mime_type": match.group(1), "data": match.group(2)}})
    if len(parts) == 1: return ""
    for model in models:
        try:
            response = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent", headers={"x-goog-api-key": key}, json={"contents": [{"parts": parts}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0.1}}, timeout=(8, 120))
            response.raise_for_status()
            result = _extract_json(response.json()["candidates"][0]["content"]["parts"][0]["text"])
            return clean_textbook_text(result.get("text", "")) if isinstance(result, dict) else ""
        except Exception:
            log.exception("Gemini vision OCR failed with %s", model)
    return ""

def _normalize(data, title, subject, raw_content):
    raw_content = clean_textbook_text(raw_content)
    fallback = _fallback(title, subject, raw_content)
    if not isinstance(data, dict): return fallback
    points = data.get("key_points")
    if not isinstance(points, list): points = fallback["key_points"]
    points = [clean_textbook_text(str(p)).strip()[:500] for p in points if str(p).strip()][:8]
    points = [p for p in points if p and not re.search(r"(?i)Sindh Textbook Board|SLO'S|^\d+\s+[A-Za-z ]+$", p)]
    if len(points) < 6: points += fallback["key_points"][:6 - len(points)]
    defs = data.get("definitions")
    if not isinstance(defs, list): defs = fallback["definitions"]
    defs = [{"term": clean_textbook_text(d.get("term", "")).strip()[:100], "definition": clean_textbook_text(d.get("definition", "")).strip()[:700]}
            for d in defs if isinstance(d, dict) and d.get("term") and d.get("definition")][:20]
    defs = [item for item in defs if item["term"] and item["definition"] and not re.search(r"(?i)Sindh Textbook Board|SLO'S|^\d+\s+[A-Za-z ]+$", item["term"])]
    if len(defs) < 6:
        existing = {item["term"].lower() for item in defs}
        defs.extend(item for item in fallback["definitions"] if item["term"].lower() not in existing)
        defs = defs[:8]
    summary = clean_textbook_text(str(data.get("summary") or fallback["summary"])).strip()[:5000]
    raw_flow = str(data.get("flowchart_mermaid") or fallback["flowchart_mermaid"]).strip()
    raw_mind = str(data.get("mindmap_mermaid") or fallback["mindmap_mermaid"]).strip()
    flow = sanitize_mermaid(raw_flow)
    mind = sanitize_mermaid(raw_mind)
    if not flow.startswith("flowchart TD"): flow = fallback["flowchart_mermaid"]
    if not mind.startswith("mindmap"): mind = fallback["mindmap_mermaid"]
    if "check understanding" in flow.lower(): flow = fallback["flowchart_mermaid"]
    if "check understanding" in mind.lower(): mind = fallback["mindmap_mermaid"]
    return {"summary": summary, "key_points": points, "definitions": defs,
            "flowchart_mermaid": flow[:12000], "mindmap_mermaid": mind[:12000]}

def _split_note_chunks(text, max_chars=12000):
    """Split long note text on paragraph/sentence boundaries with small overlap."""
    units = [part.strip() for part in re.split(r"\n\s*\n|(?<=[.!?])\s+", text or "") if part.strip()]
    chunks, current = [], ""
    for unit in units:
        while len(unit) > max_chars:
            if current:
                chunks.append(current)
                current = ""
            cut = unit.rfind(" ", 0, max_chars)
            if cut < max_chars // 2:
                cut = max_chars
            chunks.append(unit[:cut].strip())
            unit = unit[max(0, cut - 200):].strip()
        candidate = f"{current} {unit}".strip() if current else unit
        if len(candidate) > max_chars and current:
            chunks.append(current)
            current = f"{current[-200:]} {unit}".strip()
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks or [str(text or "")[:max_chars]]

def _note_analysis_prompt(title, subject, content, synthesis=False):
    instruction = (
        "Synthesize all chunk analyses into one accurate study guide for a new student. Write a clear 5 to 6 sentence Executive Summary. Return 6 to 8 complete, meaningful key_points and 6 to 8 definitions with student-friendly explanations and formulas/examples when present. Build an academic process flowchart and a mind map with 4 to 5 branches and 2 to 3 subnodes each. Exclude page numbers and watermarks."
        if synthesis else
        "Analyze this source chunk for a new student. Return complete educational points and clear definitions; preserve formulas and examples. Remove watermarks, headers, page numbers and OCR fragments."
    )
    return f'''You are an expert professor and patient tutor preparing a reliable study guide from student-provided textbook material. Use only the source content; do not guess or add outside facts. {instruction} Return JSON with exactly these keys: summary, key_points (5 to 8 detailed strings), definitions (array of objects with term and definition), flowchart_mermaid (valid Mermaid flowchart TD), mindmap_mermaid (valid Mermaid mindmap with one root and children indented by exactly two spaces per level). Use safe readable ASCII labels in diagrams, quote flowchart labels, and do not include markdown fences.\nTITLE: {title}\nSUBJECT: {subject}\nSOURCE MATERIAL:\n{content}'''

def analyze_notes_and_generate_visuals(title, subject, raw_content):
    """Create a detailed study guide, synthesizing chunks when source notes are long."""
    try:
        raw_content = clean_textbook_text(raw_content)
        if len(raw_content) <= 18000:
            result = generate_json(_note_analysis_prompt(title, subject, raw_content))
        else:
            chunk_analyses = []
            for index, chunk in enumerate(_split_note_chunks(raw_content), 1):
                analysis = generate_json(_note_analysis_prompt(title, subject, f"CHUNK {index}:\n{chunk}"))
                if isinstance(analysis, dict):
                    chunk_analyses.append({
                        "summary": str(analysis.get("summary") or "")[:1800],
                        "key_points": analysis.get("key_points") if isinstance(analysis.get("key_points"), list) else [],
                        "definitions": analysis.get("definitions") if isinstance(analysis.get("definitions"), list) else [],
                    })
            if not chunk_analyses:
                return _fallback(title, subject, raw_content)
            result = generate_json(_note_analysis_prompt(
                title, subject, json.dumps(chunk_analyses, ensure_ascii=True), synthesis=True
            ))
    except Exception:
        log.exception("Gemini note analysis failed; using deterministic note analysis")
        return _fallback(title, subject, raw_content)
    return _normalize(result, title, subject, raw_content) if result else _fallback(title, subject, raw_content)

def generate_visuals(title, subject, raw_content):
    """Regenerate/refine diagram strings while retaining a deterministic fallback."""
    result = analyze_notes_and_generate_visuals(title, subject, raw_content)
    return {"flowchart_mermaid": sanitize_mermaid(result["flowchart_mermaid"]), "mindmap_mermaid": sanitize_mermaid(result["mindmap_mermaid"])}

def _concepts(title, key_points, definitions, raw_content):
    concepts = [str(item.get("term", "")).strip() for item in (definitions or []) if isinstance(item, dict)]
    concepts += [_clean(point, 65) for point in (key_points or [])]
    concepts += [_clean(sentence, 65) for sentence in _sentences(raw_content)[:4]]
    seen = set()
    result = []
    for concept in concepts:
        clean = " ".join(concept.split())
        if clean and clean.lower() not in seen:
            seen.add(clean.lower())
            result.append(clean)
    return (result or [_clean(title, 65)])[:8]

def _assessment_fallback(title, subject, raw_content, summary, key_points, definitions, difficulty="medium"):
    concepts = _concepts(title, key_points, definitions, raw_content)
    facts = [str(point).strip() for point in (key_points or []) if str(point).strip()] or _sentences(raw_content)
    definition_items = [item for item in (definitions or []) if isinstance(item, dict) and item.get("term") and item.get("definition")]
    by_term = {str(item["term"]).strip().lower(): str(item["definition"]).strip() for item in definition_items}
    if difficulty == "easy":
        lead = "Which statement best defines"
    elif difficulty == "exam_level":
        lead = "A student is asked to apply this chapter's idea. Which statement correctly explains"
    else:
        lead = "Which statement best explains"
    questions = []
    for index, concept in enumerate(concepts[:6], 1):
        fact = facts[(index - 1) % len(facts)][:320] if facts else f"Review {concept} in the notes."
        matching = next((item for item in definition_items if str(item["term"]).strip().lower() == concept.lower()), None)
        correct_text = str(matching["definition"])[:220] if matching else fact[:220]
        if index % 2:
            distractors = [str(item["definition"])[:220] for item in definition_items if str(item["definition"]).strip() != correct_text]
            options = list(dict.fromkeys([correct_text, *distractors]))[:4]
            while len(options) < 4:
                options.append(f"This idea is not described by the chapter's notes ({len(options)}).")
            options = options[:4]
            offset = index % len(options)
            options = options[offset:] + options[:offset]
            questions.append({"id":f"q{index}","type":"mcq","question":f"{lead} {concept}?",
                              "options":options,"correct_answer":correct_text,"keywords":[word.lower() for word in re.findall(r"[A-Za-z]{4,}", concept)[:3] or [concept.lower()]],
                              "explanation":f"Step 1: Identify {concept}. Step 2: Match it to the note definition: {correct_text}","concept_tag":concept})
        else:
            keywords = [word.lower() for word in re.findall(r"[A-Za-z]{4,}", correct_text)[:5]]
            questions.append({"id":f"q{index}","type":"short","question":f"Explain {concept} in your own words and include its formula or a textbook example when one is given.",
                              "options":[],"correct_answer":correct_text,"keywords":keywords or [concept.lower()],
                              "explanation":f"A complete answer names {concept}, explains the idea, and connects it to this note point: {fact}","concept_tag":concept})
    flashcards=[]
    card_sources=definition_items[:]
    used={str(item["term"]).lower() for item in card_sources}
    for i, point in enumerate(facts):
        if len(card_sources)>=8: break
        term=concepts[i%len(concepts)] if concepts else f"Key idea {i+1}"
        if term.lower() not in used:
            card_sources.append({"term":term,"definition":point});used.add(term.lower())
    while len(card_sources)<6:
        idx=len(card_sources);card_sources.append({"term":f"Review point {idx+1}","definition":facts[idx%len(facts)] if facts else summary or title})
    for index,item in enumerate(card_sources[:8],1):
        term=str(item["term"]).strip(); explanation=str(item["definition"]).strip()
        flashcards.append({"id":f"f{index}","front":f"Explain {term}. Include the related formula or example if the notes provide one.","back":explanation,
                           "concept_tag":term,"difficulty":difficulty})
    return {"questions":questions,"flashcards":flashcards}

def generate_quiz_and_flashcards(title, subject, raw_content, summary, key_points, definitions, difficulty="medium"):
    """Generate 5–8 mixed questions and 6–10 flashcards, with an offline fallback."""
    difficulty = difficulty if difficulty in ("easy", "medium", "exam_level") else "medium"
    fallback = _assessment_fallback(title, subject, raw_content, summary, key_points, definitions, difficulty)
    prompt = f'''Create a high-quality, student-friendly {difficulty.replace('_',' ')} study assessment. Use complete questions, four distinct plausible options for every MCQ, and step-by-step explanations that state why the answer is correct. Include formulas and note examples where relevant. Return JSON only with keys questions and flashcards. questions must contain 5–8 objects with id, type (mcq or short), question, options (four strings for mcq or [] for short), correct_answer (exact option text for MCQ), keywords (array), explanation, concept_tag. flashcards must contain 6–8 objects with id, front, back (clear explanation with formula/example when present), concept_tag, difficulty. Only ask answerable questions from the notes.\nTITLE: {title}\nSUBJECT: {subject}\nSUMMARY: {summary}\nKEY POINTS: {json.dumps(key_points)}\nDEFINITIONS: {json.dumps(definitions)}\nNOTES: {raw_content}'''
    try:
        data = generate_json(prompt)
        if not isinstance(data, dict) or not isinstance(data.get("questions"), list) or not isinstance(data.get("flashcards"), list):
            return fallback
        questions = []
        for index, question in enumerate(data["questions"][:8], 1):
            if not isinstance(question, dict) or question.get("type") not in ("mcq", "short") or not question.get("question"):
                continue
            kind = question["type"]
            options = question.get("options") if kind == "mcq" else []
            if kind == "mcq" and (not isinstance(options, list) or len(options) != 4 or len({str(option).strip().lower() for option in options}) != 4):
                continue
            questions.append({"id": str(question.get("id") or f"q{index}"), "type": kind, "question": str(question["question"])[:600],
                              "options": [str(option)[:200] for option in options[:4]], "correct_answer": str(question.get("correct_answer", ""))[:300],
                              "keywords": [str(word).lower()[:80] for word in question.get("keywords", []) if str(word).strip()][:6],
                              "explanation": str(question.get("explanation") or "Step 1: Identify the concept asked about. Step 2: Match it to the supporting note definition or example.")[:700], "concept_tag": str(question.get("concept_tag") or title)[:120]})
        cards = [{"id": str(card.get("id") or f"f{i}"), "front": str(card.get("front", ""))[:500], "back": str(card.get("back", ""))[:900],
                  "concept_tag": str(card.get("concept_tag") or title)[:120], "difficulty": str(card.get("difficulty") or "medium")[:40]}
                 for i, card in enumerate(data["flashcards"][:10], 1) if isinstance(card, dict) and card.get("front") and card.get("back")]
        return {"questions": questions, "flashcards": cards} if len(questions) >= 5 and len(cards) >= 6 else fallback
    except Exception:
        log.exception("Gemini assessment request failed; using deterministic assessment")
        return fallback

def _gap_fallback(title, subject, raw_content, wrong_answers):
    gaps = []
    for item in wrong_answers or []:
        topic = _clean(item.get("concept_tag") or item.get("question") or title, 80)
        if any(existing["weak_topic"].lower() == topic.lower() for existing in gaps):
            continue
        expected = str(item.get("correct_answer") or "the relevant idea from your notes")
        gaps.append({"weak_topic": topic, "status": "needs_practice",
                     "simple_explanation": f"{topic} is a key part of {title}. Revisit how it relates to {expected} in your notes.",
                     "recommended_action": "1. Read the simplified explanation. 2. Trace the recovery flowchart. 3. Retry one quiz question and two flashcards.",
                     "mini_flowchart": sanitize_mermaid(f"flowchart TD\n  A[\"Review {topic}\"] --> B[\"Read a simple explanation\"]\n  B --> C[\"Practice one example\"]\n  C --> D[\"Retry the question\"]")})
    return gaps[:6]

def detect_knowledge_gaps(title, subject, raw_content, wrong_answers):
    """Identify weak concepts after an attempt; always returns Mermaid-safe recovery steps."""
    fallback = _gap_fallback(title, subject, raw_content, wrong_answers)
    if not fallback:
        return []
    prompt = f'''Analyze these missed study answers. Return a JSON array of objects with weak_topic, status set to needs_practice, simple_explanation, recommended_action with three steps, and mini_flowchart as Mermaid flowchart TD. Use only facts from the notes and clean ASCII Mermaid labels.\nTITLE: {title}\nSUBJECT: {subject}\nNOTES: {raw_content}\nMISSED ANSWERS: {json.dumps(wrong_answers)}'''
    try:
        data = generate_json(prompt)
        if not isinstance(data, list): return fallback
        clean = []
        for index, gap in enumerate(data[:6]):
            if not isinstance(gap, dict) or not gap.get("weak_topic"): continue
            flow = sanitize_mermaid(str(gap.get("mini_flowchart", "")))
            fallback_flow = fallback[min(index, len(fallback)-1)]["mini_flowchart"]
            clean.append({"weak_topic": str(gap["weak_topic"])[:120], "status": "needs_practice",
                          "simple_explanation": str(gap.get("simple_explanation") or fallback[min(index, len(fallback)-1)]["simple_explanation"])[:1200],
                          "recommended_action": str(gap.get("recommended_action") or fallback[min(index, len(fallback)-1)]["recommended_action"])[:1200],
                          "mini_flowchart": flow[:6000] if flow.startswith("flowchart TD") else fallback_flow})
        return clean or fallback
    except Exception:
        log.exception("Gemini gap detection failed; using deterministic recovery plan")
        return fallback

def _note_passages(note):
    passages = [("Summary", str(note.get("summary") or ""))]
    points = note.get("key_points") or []
    if isinstance(points, dict): points = list(points.values())
    if not isinstance(points, list): points = []
    for i, point in enumerate(points, 1): passages.append((f"Key point {i}", str(point)))
    definitions = note.get("definitions") or []
    if isinstance(definitions, dict):
        definitions = [{"term": key, "definition": value} for key, value in definitions.items()]
    if not isinstance(definitions, list): definitions = []
    for definition in definitions:
        if isinstance(definition, dict): passages.append((f"Definition: {definition.get('term', 'concept')}", f"{definition.get('term', '')}: {definition.get('definition', '')}"))
    raw_content = str(note.get("raw_content") or "")
    chunks = []
    for section in re.split(r"\n\s*\n|(?<=[.!?])\s+(?=[A-Z])", raw_content):
        section = section.strip()
        while len(section) > 900:
            split_at = section.rfind(" ", 0, 900)
            if split_at < 400: split_at = 900
            chunks.append(section[:split_at].strip())
            section = section[split_at:].strip()
        if section: chunks.append(section)
    for i, chunk in enumerate(chunks, 1):
        passages.append((f"Notes section {i}", chunk))
    return passages

def _keywords(text):
    return {word.lower() for word in re.findall(r"\b(?:[KQ]c|[A-Za-z]{3,})\b", text, re.I)}

def answer_from_notes_rag(note, question, chat_history=None):
    """Retrieve note passages and answer strictly from them, with a Hinglish-friendly fallback."""
    query = _keywords(question)
    # Supply the complete note guide plus keyword-ranked source passages so short Roman Urdu
    # questions still receive the context embedded in the generated definitions and points.
    ranked = sorted(_note_passages(note), key=lambda item: len(query & _keywords(item[1])), reverse=True)
    top = [item for item in ranked if item[1]][:3]
    if not top: top = [("Notes", "No usable note content was found.")]
    context = "\n".join(f"{heading}: {text[:1400]}" for heading, text in ranked[:10] if text)
    title = str(note.get("title") or "Your note")
    excerpt = re.sub(r"\s+", " ", top[0][1]).strip()[:180]
    reference = f"{note.get('subject') or 'Study notes'} — {title} | Section: {top[0][0]} (Excerpt: '{excerpt}')"
    prompt = f'''You are a patient study tutor. Answer the student's question using only the selected note context. Use simple English or Roman Urdu/Hinglish matching the question. Structure the answer with a short main idea, numbered steps when explaining a process, and a Formula / Example section when the note provides one. For a request for five questions, give five short questions with their answers from the notes. Do not invent facts. Return JSON with answer and suggested_followups (three short questions).\nQUESTION: {question}\nNOTE CONTEXT:\n{context}'''
    try:
        result = generate_json(prompt)
        if isinstance(result, dict) and result.get("answer"):
            followups = [str(item)[:180] for item in result.get("suggested_followups", []) if str(item).strip()][:3]
            return {"answer": str(result["answer"])[:5000], "source_reference": reference, "suggested_followups": followups or ["Summarize the main steps", "Which definition should I remember?", "Quiz me on this concept"]}
    except Exception:
        log.exception("Gemini RAG request failed; using grounded fallback")
    roman_urdu = bool(re.search(r"\b(ko|mein|samjhao|kya|kaise|hai|aur|batao)\b", question.lower()))
    lead = "Asaan alfaaz mein" if roman_urdu else "In simple terms"
    point_passages = [(heading, text) for heading, text in ranked if heading.startswith(("Key point", "Definition")) and text]
    if re.search(r"\b5\b|five|paanch", question.lower()) and re.search(r"question|sawal|short questions", question.lower()):
        qa = point_passages[:5] or top[:5]
        answer = "Important short questions with note-based answers:\n" + "\n".join(f"{index}. What should you know about {heading.replace('Definition: ', '')}?\n   Answer: {text[:420]}" for index, (heading, text) in enumerate(qa, 1))
    else:
        ideas = point_passages[:4] or top[:3]
        formulas = [text for _, text in ranked if re.search(r"(?:=|->|<=>|\bKc\b|\bQc\b|\d+\s*[x×])", text, re.I)][:2]
        answer = f"{lead}:\n" + "\n".join(f"- {text[:700]}" for _, text in ideas)
        answer += "\n\nFormula / Example:\n" + ("\n".join(f"- {text[:500]}" for text in formulas) if formulas else "- No formula or worked example is stated in this note section.")
        answer += "\n\nStudy step: connect the definition to the example, then check the relevant formula against the question."
    return {"answer": answer[:5000], "source_reference": reference,
            "suggested_followups": ["Summarize the main steps", "What are the key definitions?", "Can you quiz me on this topic?"]}

def generate_smart_revision_plan(exam_date, daily_hours, notes, knowledge_gaps, quiz_attempts, exam_title="Matric Exam", priority_focus="saved_and_weak"):
    """Build a 3–14 day, gap-first revision schedule from student-owned data."""
    target = date.fromisoformat(str(exam_date)); today = date.today()
    days = max(3, min(14, (target - today).days if target > today else 3))
    hours = max(1, min(8, int(daily_hours)))
    gaps = [gap for gap in knowledge_gaps if gap.get("status") == "needs_practice"]
    score_by_note = {}
    for attempt in quiz_attempts:
        if attempt.get("total_questions"):
            ratio = attempt.get("score", 0) / attempt["total_questions"]
            score_by_note[attempt.get("note_id")] = min(score_by_note.get(attempt.get("note_id"), 1), ratio)
    gap_note_ids = [gap.get("note_id") for gap in gaps if gap.get("note_id")]
    ordered = sorted(notes, key=lambda item: (0 if priority_focus in ("saved_and_weak", "weak_concepts") and item.get("id") in gap_note_ids else 1, score_by_note.get(item.get("id"), .75), item.get("title", ""))) or [{"id": None, "title": "Active recall review"}]
    schedule = []
    for number in range(1, days + 1):
        note = ordered[(number - 1) % len(ordered)]
        gap = next((item for item in gaps if item.get("note_id") == note.get("id")), None)
        final = number == days
        priority = "Final - Active Recall & Mock Quiz" if final else ("High - Knowledge Gap" if gap else "Medium - Core Concept Review")
        focus = gap.get("weak_topic") if gap else note.get("title", "Core review")
        topic = note.get("title", "this chapter")
        tasks = [{"id": f"d{number}_t1", "text": f"Read key concepts and formulas for {focus} (30 min)", "type": "concepts", "done": False},
                 {"id": f"d{number}_t2", "text": f"Practice examples, numericals, or derivations from {topic} (30 min)", "type": "practice", "done": False},
                 {"id": f"d{number}_t3", "text": "Use active-recall flashcards and a short quiz (20 min)", "type": "recall", "done": False}]
        schedule.append({"day_number": number, "date": str(today + timedelta(days=number - 1)), "focus_title": focus, "note_id": note.get("id"), "note_title": topic, "priority": priority, "allocated_hours": f"{hours} hour{'s' if hours != 1 else ''}", "exam_title": str(exam_title or "Matric Exam")[:120], "priority_focus": priority_focus, "exam_tip": "Exam tip: define the concept, show the relevant formula, then explain what the result means.", "tasks": tasks})
    return {"summary_advice": f"You have {days} study days with {hours} hour(s) each. Start with {len(gaps)} knowledge-gap topic(s), then use active recall to consolidate stronger material.", "schedule": schedule}
