"""
Phase 1: Architecture Crew
Researcher -> Analyst -> Reviewer (with reflection loop)

Uses CrewAI for orchestration, direct API calls for tools.
Outputs a structured workflow design for human review before coding phase.
"""

import json
import time
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import load_agents_config, get_llm_config, call_llm
from tools import tavily_search, pubmed_search


# ---------------------------------------------------------------------------
# CrewAI Tool wrappers (bridge direct API tools to CrewAI interface)
# ---------------------------------------------------------------------------

class TavilySearchTool(BaseTool):
    name: str = "Web Search"
    description: str = (
        "Search the web for bioinformatics tools, papers, and benchmarks. "
        "Input should be a search query string."
    )

    def _run(self, query: str) -> str:
        result = tavily_search.search(query, max_results=5)
        output = f"Answer: {result['answer']}\n\nSources:\n"
        for r in result["results"]:
            output += f"- [{r['title']}]({r['url']})\n  {r['content'][:200]}\n"
        return output


class PubMedSearchTool(BaseTool):
    name: str = "PubMed Search"
    description: str = (
        "Search PubMed for peer-reviewed biomedical papers. "
        "Input should be a search query string."
    )

    def _run(self, query: str) -> str:
        articles = pubmed_search.search_pubmed(query, max_results=5)
        if not articles:
            return "No PubMed results found."
        output = ""
        for a in articles:
            output += (
                f"- PMID:{a['pmid']} ({a['year']}) {a['title']}\n"
                f"  {a['authors']} - {a['journal']}\n"
                f"  {a['abstract'][:200]}...\n\n"
            )
        return output


# ---------------------------------------------------------------------------
# Architecture Crew builder
# ---------------------------------------------------------------------------

def build_architecture_crew(
    task_description: str = "UMI-based 16S rRNA clustering for metatranscriptomic abundance",
    verbose: bool = True,
) -> Crew:
    """
    Build Phase 1 crew: Researcher -> Analyst -> Reviewer.

    Args:
        task_description: The biological question / pipeline goal
        verbose: Print agent reasoning

    Returns:
        CrewAI Crew object ready to kickoff
    """
    config = load_agents_config()
    arch_config = config["architecture_crew"]
    crew_settings = config.get("crew", {})

    # Create CrewAI LLM instance based on config
    from crewai import LLM
    import os
    
    def get_agent_llm(agent_cfg):
        llm_cfg = agent_cfg.get("llm", config.get("llm_defaults", {}))
        provider = llm_cfg.get("provider", "xai")
        model = llm_cfg.get("model", "grok-3-mini-fast")
        temperature = llm_cfg.get("temperature", 0.3)
        
        if provider == "xai":
            return LLM(
                model=f"xai/{model}",
                api_key=os.getenv("GROK_API_KEY"),
                temperature=temperature
            )
        elif provider == "deepseek":
            return LLM(
                model=f"deepseek/{model}",
                api_key=os.getenv("DEEPSEEK_API_KEY"),
                temperature=temperature
            )
        else:
            return LLM(model=model, temperature=temperature)

    # Instantiate tools
    tavily_tool = TavilySearchTool()
    pubmed_tool = PubMedSearchTool()

    # --- Researcher Agent ---
    res_cfg = arch_config["researcher"]
    researcher = Agent(
        role=res_cfg["role"],
        goal=res_cfg["goal"],
        backstory=res_cfg["backstory"],
        tools=[tavily_tool, pubmed_tool],
        verbose=verbose,
        memory=crew_settings.get("memory", True),
        llm=get_agent_llm(res_cfg)
    )

    # --- Analyst Agent ---
    ana_cfg = arch_config["analyst"]
    analyst = Agent(
        role=ana_cfg["role"],
        goal=ana_cfg["goal"],
        backstory=ana_cfg["backstory"],
        tools=[],
        verbose=verbose,
        memory=crew_settings.get("memory", True),
        llm=get_agent_llm(ana_cfg)
    )

    # --- Reviewer Agent ---
    rev_cfg = arch_config["reviewer"]
    reviewer = Agent(
        role=rev_cfg["role"],
        goal=rev_cfg["goal"],
        backstory=rev_cfg["backstory"],
        tools=[tavily_tool],
        verbose=verbose,
        memory=crew_settings.get("memory", True),
        llm=get_agent_llm(rev_cfg)
    )

    # --- Tasks ---
    task_research = Task(
        description=(
            f"Topic: {task_description}\n\n"
            "1. Search for the latest tools, methods, and best practices (2023-2026) "
            "relevant to the topic.\n"
            "2. Search PubMed for recent benchmarking papers or foundational methodologies.\n"
            "3. Summarize the top 3-5 tools/methods with: name, version, key features, limitations.\n"
            "4. Summarize the top 3 papers with: title, year, key findings.\n"
            "5. Note any consensus on best practices."
        ),
        expected_output=(
            "A structured summary with:\n"
            "- Tool/method recommendations table (name, purpose, pros/cons)\n"
            "- Paper summaries (title, year, key findings)\n"
            "- Best practices consensus"
        ),
        agent=researcher,
    )

    task_design = Task(
        description=(
            f"Based on the Researcher's findings for the topic: {task_description}, "
            "design a complete, step-by-step bioinformatics workflow:\n\n"
            "1. Input specification (e.g., data format, structure, layout)\n"
            "2. Step-by-step pipeline from raw data to final analysis\n"
            "3. Output specification (e.g., tables, metrics, visualizations)\n"
            "4. For each step: tool choice, detailed parameters, rationale vs alternatives\n"
            "5. Integration plan with existing systems or pipelines\n"
            "6. Edge cases: how to handle low-quality data or specific domain challenges"
        ),
        expected_output=(
            "A detailed workflow document with:\n"
            "- Pipeline flowchart (text-based)\n"
            "- Per-step: tool, input, output, parameters, rationale\n"
            "- Integration plan\n"
            "- Edge case handling"
        ),
        agent=analyst,
        output_file="outputs/analyst_design.md"
    )

    task_review = Task(
        description=(
            "Review the Analyst's proposed workflow for scientific rigor, "
            "reproducibility, and completeness.\n\n"
            "1. Verify tool choices are appropriate and parameters are explicitly defined.\n"
            "2. Check if edge cases are handled robustly.\n"
            "3. Ensure the workflow is practical and can be integrated as planned.\n"
            "4. Score the workflow (0-10) on: completeness, accuracy, practicality, innovation.\n"
            "5. Provide an overall score.\n"
            "6. Detail strengths and weaknesses.\n"
            "7. List specific improvements with priority (high/medium/low).\n\n"
            "If the overall score is below 7, provide detailed feedback for revision.\n"
            "IMPORTANT: Your final output MUST include the full, corrected workflow steps "
            "and parameters from the Analyst, in addition to your review scores and comments."
        ),
        expected_output=(
            "A structured review containing:\n"
            "- The complete, final approved workflow (with all steps and parameters)\n"
            "- Scores (completeness, accuracy, practicality, innovation)\n"
            "- Overall score (0-10)\n"
            "- Strengths and weaknesses\n"
            "- Prioritized improvements list\n"
            "- PASS/REVISE verdict"
        ),
        agent=reviewer,
        output_file="outputs/reviewer_feedback.md"
    )

    crew = Crew(
        agents=[researcher, analyst, reviewer],
        tasks=[task_research, task_design, task_review],
        process=Process.sequential,
        verbose=verbose,
        memory=crew_settings.get("memory", True),
    )

    return crew


def run_architecture_phase(
    task_description: str = "UMI-based 16S rRNA clustering for metatranscriptomic abundance",
    output_dir: str = "outputs",
    verbose: bool = True,
) -> Dict:
    """
    Run Phase 1 and save results. Returns structured output for human review.
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    crew = build_architecture_crew(task_description, verbose=verbose)

    print(f"\n{'='*60}")
    print(f"Phase 1: Architecture Crew")
    print(f"Task: {task_description}")
    print(f"{'='*60}\n")

    start = time.time()
    result = crew.kickoff()
    elapsed = time.time() - start

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = {
        "phase": "architecture",
        "task": task_description,
        "timestamp": timestamp,
        "elapsed_seconds": round(elapsed, 1),
        "result": str(result),
    }

    outfile = output_path / f"architecture_{timestamp}.json"
    with open(outfile, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    # Also save as readable markdown
    md_file = output_path / f"architecture_{timestamp}.md"
    with open(md_file, "w") as f:
        f.write(f"# Architecture Design: {task_description}\n\n")
        f.write(f"*Generated: {timestamp} ({elapsed:.1f}s)*\n\n")
        f.write(str(result))

    print(f"\nResults saved to: {outfile}")
    print(f"Markdown saved to: {md_file}")
    print(f"Elapsed: {elapsed:.1f}s")
    print(f"\n>>> Review the output, then run Phase 2 (coding) <<<\n")

    return output
