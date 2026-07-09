import time
import re
from pathlib import Path
import httpx

EXTRACTED_DIR = Path("extracted")
EXTRACTED_DIR.mkdir(exist_ok=True)


async def process_github(username: str) -> dict:
    repos = await _fetch_repos(username)

    if not repos:
        return {"error": f"No public repos found for '{username}'"}

    readme_limit = 5 if len(repos) >= 5 else max(1, len(repos) - 1) if len(repos) > 1 else 1
    if len(repos) < 5:
        readme_limit = min(8, len(repos))

    readmes = await _fetch_readmes(username, repos, readme_limit)
    lang_stats = _aggregate_languages(repos)
    all_topics = _collect_topics(repos)
    skills = _extract_skills(readmes, all_topics)

    content = _format_output(username, repos, lang_stats, all_topics, readmes, skills)
    ts = str(int(time.time()))
    out_path = EXTRACTED_DIR / f"github_{username}_{ts}.txt"
    out_path.write_text(content)

    return {
        "username": username,
        "repo_count": len(repos),
        "readmes_fetched": len(readmes),
        "languages": lang_stats,
        "topics": all_topics,
        "skills": skills,
        "saved_as": str(out_path),
        "content": content,
    }


async def _fetch_repos(username: str) -> list:
    url = f"https://api.github.com/users/{username}/repos?per_page=100&sort=updated&type=all"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, headers={"Accept": "application/vnd.github.v3+json"})
        if resp.status_code == 404:
            return []
        if resp.status_code != 200:
            return []
        return resp.json()


async def _fetch_readmes(username: str, repos: list, limit: int) -> list:
    results = []
    async with httpx.AsyncClient(timeout=10.0) as client:
        for repo in repos[:limit]:
            name = repo["name"]
            default_branch = repo.get("default_branch", "main")
            readme_url = f"https://raw.githubusercontent.com/{username}/{name}/{default_branch}/README.md"
            try:
                resp = await client.get(readme_url, timeout=8.0)
                if resp.status_code == 200 and resp.text.strip():
                    summary = _summarize_readme(resp.text)
                    results.append({
                        "name": name,
                        "description": repo.get("description") or "",
                        "topics": repo.get("topics", []),
                        "language": repo.get("language"),
                        "stars": repo["stargazers_count"],
                        "readme_summary": summary,
                    })
            except (httpx.TimeoutException, httpx.ConnectError):
                pass
    return results


def _summarize_readme(raw: str) -> str:
    cleaned = re.sub(r"<!--.*?-->", "", raw, flags=re.DOTALL)
    cleaned = re.sub(r"```[\s\S]*?```", "", cleaned)
    cleaned = re.sub(r"#{1,6}\s+", "", cleaned)
    cleaned = re.sub(r"[*_~`]", "", cleaned)
    cleaned = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)

    lines = [l.strip() for l in cleaned.splitlines() if l.strip()]
    important = []
    keywords = {"install", "usage", "api", "feature", "example", "setup",
                "technolog", "built with", "dependenc", "config", "architect"}

    for line in lines:
        if len(line) < 15:
            continue
        lower = line.lower()
        if any(kw in lower for kw in keywords):
            important.append(line)
        elif len(important) < 3:
            important.append(line)

    text = " | ".join(important[:5]) if important else (lines[0] if lines else "")
    if len(text) > 800:
        text = text[:800] + "..."

    return text


def _aggregate_languages(repos: list) -> list:
    counts = {}
    for r in repos:
        lang = r.get("language")
        if lang:
            counts[lang] = counts.get(lang, 0) + 1

    if not counts:
        return []

    total = sum(counts.values())
    sorted_langs = sorted(counts.items(), key=lambda x: -x[1])
    return [{"language": lang, "repos": count, "percentage": round(count / total * 100)} for lang, count in sorted_langs]


def _collect_topics(repos: list) -> list:
    seen = set()
    topics = []
    for r in repos:
        for t in r.get("topics", []):
            if t not in seen:
                seen.add(t)
                topics.append(t)
    return topics


def _extract_skills(readmes: list, topics: list) -> list:
    known_skills = {
        "python", "javascript", "typescript", "react", "node.js", "node",
        "fastapi", "django", "flask", "docker", "kubernetes", "aws", "gcp",
        "azure", "postgresql", "postgres", "mysql", "mongodb", "redis",
        "graphql", "rest", "rest api", "machine learning", "deep learning",
        "tensorflow", "pytorch", "ci/cd", "git", "linux", "terraform",
        "ansible", "jenkins", "html", "css", "sass", "tailwind", "bootstrap",
        "vue", "angular", "sql", "nosql", "microservices", "serverless",
        "go", "golang", "rust", "java", "ruby", "c++", "c#", "php", "swift",
        "kotlin", "flutter", "dart", "react native", "next.js", "express",
        "spring", "laravel", "rails", "redux", "webpack", "jest",
        "pandas", "numpy", "scikit-learn", "keras", "opencv",
        "hadoop", "spark", "kafka", "nginx", "github actions",
        "prometheus", "grafana", "elasticsearch", "datadog",
    }

    tech_pattern = re.compile(
        r"\b(py|js|ts|api|sdk|cli|db|sql|nosql|ai|ml|dl|ui|ux|ci|cd|"
        r"devops|backend|frontend|fullstack|web|mobile|cloud|native|"
        r"microservice|serverless|container|orm|rest|graphql)\b",
        re.IGNORECASE,
    )

    skills = set()
    for t in topics:
        tl = t.lower().replace("-", " ").replace("_", " ")
        if tl in known_skills:
            skills.add(tl)
        elif tech_pattern.search(tl) and len(tl) < 25:
            skills.add(tl)

    for readme in readmes:
        text = (readme.get("readme_summary") or "") + " " + (readme.get("description") or "")
        lower = text.lower()
        for skill in known_skills:
            if skill in lower:
                skills.add(skill)

    return sorted(skills, key=lambda s: -len(s))


def _format_output(username: str, repos: list, lang_stats: list, topics: list, readmes: list, skills: list) -> str:
    lines = []
    lines.append(f"[GITHUB PROFILE]")
    lines.append(f"Username: {username}")
    lines.append(f"Public Repos: {len(repos)}")
    if lang_stats:
        lang_line = ", ".join(f"{l['language']} ({l['percentage']}%)" for l in lang_stats[:8])
        lines.append(f"Top Languages: {lang_line}")
    if topics:
        lines.append(f"Topics: {', '.join(topics[:15])}")
    lines.append("")

    if skills:
        lines.append("[DETECTED SKILLS]")
        lines.append(", ".join(skills))
        lines.append("")

    if readmes:
        lines.append("[README SUMMARIES]")
        for r in readmes:
            lines.append(f"")
            lines.append(f"Repo: {r['name']}")
            if r["description"]:
                lines.append(f"  Description: {r['description']}")
            if r["language"]:
                lines.append(f"  Language: {r['language']}")
            if r["topics"]:
                lines.append(f"  Topics: {', '.join(r['topics'])}")
            if r["readme_summary"]:
                lines.append(f"  README: {r['readme_summary']}")
        lines.append("")

    lines.append(f"[FETCHED {len(readmes)} README{'S' if len(readmes) != 1 else ''}]")
    return "\n".join(lines)
