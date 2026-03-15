"""
Phase 2: Coding Crew
Coder -> code-Reviewer (with reflection loop)

Runs after human review of Phase 1 architecture output.
Takes the approved workflow design and generates implementation code.
"""

import json
import time
import subprocess
from pathlib import Path
from typing import Dict
from datetime import datetime

from crewai import Agent, Task, Crew, Process
from crewai.tools import BaseTool

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))
from config import load_agents_config


# ---------------------------------------------------------------------------
# CrewAI Tool wrappers
# ---------------------------------------------------------------------------

class CodeExecutionTool(BaseTool):
    name: str = "Code Execution"
    description: str = (
        "Execute a Python code snippet to test syntax and basic correctness. "
        "Input should be valid Python code as a string. "
        "Returns stdout/stderr. Use for validation only, not production runs."
    )

    def _run(self, code: str) -> str:
        try:
            result = subprocess.run(
                ["python", "-c", code],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = ""
            if result.stdout:
                output += f"STDOUT:\n{result.stdout[:1000]}\n"
            if result.stderr:
                output += f"STDERR:\n{result.stderr[:1000]}\n"
            if result.returncode != 0:
                output += f"Exit code: {result.returncode}\n"
            return output if output else "Code executed successfully (no output)."
        except subprocess.TimeoutExpired:
            return "ERROR: Code execution timed out (30s limit)."
        except Exception as e:
            return f"ERROR: {str(e)}"


# ---------------------------------------------------------------------------
# Coding Crew builder
# ---------------------------------------------------------------------------

def _extract_requirements_from_architecture(architecture_doc: str) -> str:
    """
    Extract implementation requirements from Phase 1 architecture output.
    Makes the coding crew generic for any task, not hardcoded to 16S.
    """
    # Include existing code context if available
    project_root = Path(__file__).parent.parent.parent.parent
    existing_context = ""
    for fname in ["rna_16s.smk", "align_ref.py", "rna_16s.py"]:
        candidates = list(project_root.rglob(fname))
        if candidates:
            try:
                content = candidates[0].read_text()
                existing_context += f"\n--- {fname} ---\n{content[:2000]}\n"
            except Exception:
                pass
    
    return (
        f"Implement the following approved workflow as Python code.\n\n"
        f"=== APPROVED ARCHITECTURE ===\n{architecture_doc}\n"
        f"=== END ARCHITECTURE ===\n\n"
        f"=== EXISTING CODE CONTEXT ===\n{existing_context}\n"
        f"=== END CONTEXT ===\n\n"
        "Instructions:\n"
        "1. Generate complete Python code based on the architecture above\n"
        "2. Use argparse for CLI interface\n"
        "3. Proper error handling and logging\n"
        "4. Test the code syntax with the Code Execution tool"
    )


def build_coding_crew(
    architecture_doc: str,
    existing_code_context: str = "",
    verbose: bool = True,
) -> Crew:
    """
    Build Phase 2 crew: Coder -> code-Reviewer.

    Args:
        architecture_doc: Approved architecture design from Phase 1
        existing_code_context: Existing code files for reference
        verbose: Print agent reasoning

    Returns:
        CrewAI Crew object ready to kickoff
    """
    config = load_agents_config()
    code_config = config["coding_crew"]
    crew_settings = config.get("crew", {})

    code_exec_tool = CodeExecutionTool()

    # --- Coder Agent ---
    coder_cfg = code_config["coder"]
    coder = Agent(
        role=coder_cfg["role"],
        goal=coder_cfg["goal"],
        backstory=coder_cfg["backstory"],
        tools=[code_exec_tool],
        verbose=verbose,
        memory=crew_settings.get("memory", True),
    )

    # --- Code Reviewer Agent ---
    rev_cfg = code_config["code_reviewer"]
    code_reviewer = Agent(
        role=rev_cfg["role"],
        goal=rev_cfg["goal"],
        backstory=rev_cfg["backstory"],
        tools=[code_exec_tool],
        verbose=verbose,
        memory=crew_settings.get("memory", True),
    )

    # --- Tasks ---
    # Extract implementation requirements from architecture
    task_description = _extract_requirements_from_architecture(architecture_doc)
    
    task_code = Task(
        description=task_description,
        expected_output=(
            "Complete Python source code implementation based on the architecture.\n"
            "Include: main module, CLI interface, proper error handling and logging.\n"
            "Test code syntax with the Code Execution tool."
        ),
        agent=coder,
    )

    task_review = Task(
        description=(
            "Review the Coder's implementation:\n\n"
            "1. Syntax check: Run key code snippets with Code Execution tool\n"
            "2. Logic check: Verify implementation matches architecture requirements\n"
            "3. Error handling: Missing try/except, unhandled edge cases\n"
            "4. Style: Consistent with existing codebase\n"
            "5. Dependencies: All imports available? New deps documented?\n"
            "6. Score (0-10): correctness, completeness, style, integration\n"
            "7. If score < 7, provide specific fix instructions for the Coder."
        ),
        expected_output=(
            "Structured code review with:\n"
            "- Scores (correctness, completeness, style, integration)\n"
            "- Bug list with fixes\n"
            "- PASS/REVISE verdict\n"
            "- Final corrected code if REVISE"
        ),
        agent=code_reviewer,
    )

    crew = Crew(
        agents=[coder, code_reviewer],
        tasks=[task_code, task_review],
        process=Process.sequential,
        verbose=verbose,
        memory=crew_settings.get("memory", True),
    )

    return crew


def run_coding_phase(
    architecture_file: str,
    output_dir: str = "outputs",
    verbose: bool = True,
) -> Dict:
    """
    Run Phase 2: read approved architecture, generate code.

    Args:
        architecture_file: Path to Phase 1 output (JSON or MD)
        output_dir: Directory for output files
        verbose: Print agent reasoning
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Load architecture
    arch_path = Path(architecture_file)
    if arch_path.suffix == ".json":
        with open(arch_path) as f:
            arch_data = json.load(f)
        architecture_doc = arch_data.get("result", "")
    else:
        with open(arch_path) as f:
            architecture_doc = f.read()

    # Build crew - existing context is now extracted from architecture in _extract_requirements_from_architecture
    crew = build_coding_crew(architecture_doc, verbose=verbose)

    print(f"\n{'='*60}")
    print(f"Phase 2: Coding Crew")
    print(f"Architecture: {architecture_file}")
    print(f"{'='*60}\n")

    start = time.time()
    result = crew.kickoff()
    elapsed = time.time() - start

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = {
        "phase": "coding",
        "architecture_file": str(architecture_file),
        "timestamp": timestamp,
        "elapsed_seconds": round(elapsed, 1),
        "result": str(result),
    }

    outfile = output_path / f"coding_{timestamp}.json"
    with open(outfile, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    md_file = output_path / f"coding_{timestamp}.md"
    with open(md_file, "w") as f:
        f.write(f"# Code Implementation\n\n")
        f.write(f"*Generated: {timestamp} ({elapsed:.1f}s)*\n\n")
        f.write(str(result))

    print(f"\nResults saved to: {outfile}")
    print(f"Markdown saved to: {md_file}")
    print(f"Elapsed: {elapsed:.1f}s")

    return output
