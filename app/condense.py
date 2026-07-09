import re

from .config import MAX_CV_CHARS


def condense_cv_text(raw: str) -> str:
    lines = raw.splitlines()
    cleaned = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if len(line) < 3:
            continue
        cleaned.append(line)

    text = "\n".join(cleaned)

    section_keywords = [
        "skill", "experience", "education", "summary", "profile",
        "project", "certification", "achievement", "work history",
        "employment", "objective", "qualification", "language",
        "technolog", "tool", "framework", "position", "role",
    ]

    lines = text.splitlines()
    sections = []
    current = []
    current_label = "general"
    for line in lines:
        lower = line.lower()
        is_header = any(kw in lower for kw in section_keywords) and len(line) < 60
        if is_header:
            if current:
                sections.append((current_label, "\n".join(current)))
            current = []
            current_label = line.strip().rstrip(":")
        else:
            current.append(line)
    if current:
        sections.append((current_label, "\n".join(current)))

    priority = {"skill": 0, "experience": 0, "summary": 1, "profile": 1, "education": 2, "project": 3, "certification": 3}
    sections.sort(key=lambda s: priority.get(s[0].lower(), 5))

    result_parts = []
    char_count = 0
    for label, content in sections:
        block = f"[{label}]\n{content}" if label != "general" else content
        if char_count + len(block) > MAX_CV_CHARS:
            remaining = MAX_CV_CHARS - char_count
            if remaining > 100:
                result_parts.append(block[:remaining])
            break
        result_parts.append(block)
        char_count += len(block)

    final = "\n\n".join(result_parts)
    return re.sub(r"\n{3,}", "\n\n", final).strip()


def check_formatting_consistency(text: str) -> dict:
    lines = text.splitlines()
    if not lines:
        return {"score": 50, "issues": ["No content to analyze"]}

    issues = []
    passes = 0

    bullets = [l for l in lines if re.match(r"^[\s]*[-•*→▶]", l)]
    if bullets:
        markers = set()
        for b in bullets:
            m = re.search(r"^[\s]*([-•*→▶])", b)
            if m:
                markers.add(m.group(1))
        if len(markers) == 1:
            passes += 1
        else:
            issues.append(f"Inconsistent bullet markers used: {', '.join(sorted(markers))}")
    else:
        issues.append("No bullet points detected")

    headline_scores = 0
    for l in lines:
        l = l.strip()
        if len(l) > 80:
            headline_scores += 1
    long_line_ratio = headline_scores / max(len(lines), 1)
    if long_line_ratio > 0.3:
        issues.append(f"{round(long_line_ratio * 100)}% of lines exceed 80 chars — possible formatting issues")
    else:
        passes += 1

    empty_lines = sum(1 for l in lines if not l.strip())
    spacing_ratio = empty_lines / max(len(lines), 1)
    if spacing_ratio > 0.4:
        issues.append("Excessive blank lines between content")
    elif spacing_ratio < 0.05 and len(lines) > 5:
        issues.append("No blank lines between sections — may appear cramped")
    else:
        passes += 1

    body_lines = lines[2:]
    known_headers = {
        "summary", "skills", "experience", "education", "projects",
        "certifications", "publications", "languages", "interests",
        "references", "objective", "profile", "achievements",
        "employment", "work history", "qualifications", "leadership",
        "volunteering", "awards", "honors", "training", "tools",
        "technologies", "contact", "links", "portfolio",
    }
    detected_headers = 0
    suspicious_caps = 0
    for l in body_lines:
        s = l.strip()
        if not s or len(s) < 4:
            continue
        lower = s.lower().rstrip(":")
        if lower in known_headers:
            detected_headers += 1
        elif s.isupper() and len(s) > 4:
            suspicious_caps += 1
    header_density = detected_headers / max(len(body_lines), 1)
    has_structure = header_density >= 0.04 or len(body_lines) <= 8
    has_noise = suspicious_caps <= 2
    if not has_structure:
        issues.append("Few or no standard section headers detected (Summary, Skills, Experience, etc.)")
    if not has_noise:
        issues.append(f"{suspicious_caps} lines in ALL CAPS that aren't standard section headers — possible noise")
    if has_structure and has_noise:
        passes += 1

    indent_chars = set()
    for l in lines:
        s = l[:len(l) - len(l.lstrip())]
        if s:
            indent_chars.add(s[0])
    if len(indent_chars) > 2:
        issues.append(f"Inconsistent indentation characters: {', '.join(repr(c) for c in sorted(indent_chars))}")
    else:
        passes += 1

    raw_score = round((passes / 5) * 100)
    score = max(0, min(100, raw_score))

    return {"score": score, "issues": issues}
