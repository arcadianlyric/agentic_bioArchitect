"""
UMI 16S rRNA Multi-Agent Pipeline
Entry point with two-phase workflow and human-in-the-loop checkpoint.

Usage:
    # Phase 1: Architecture design
    python main.py --phase architecture --task "UMI-based 16S rRNA clustering"

    # Phase 2: Code generation (after human review)
    python main.py --phase coding --architecture outputs/architecture_YYYYMMDD_HHMMSS.json

    # Run both phases (with interactive pause)
    python main.py --phase all
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def main():
    parser = argparse.ArgumentParser(
        description="UMI 16S rRNA Multi-Agent Pipeline"
    )
    parser.add_argument(
        "--phase",
        choices=["architecture", "coding", "all"],
        default="all",
        help="Which phase to run (default: all)",
    )
    parser.add_argument(
        "--task",
        type=str,
        default="UMI-based 16S rRNA clustering for metatranscriptomic abundance analysis",
        help="Task description for Phase 1",
    )
    parser.add_argument(
        "--architecture",
        type=str,
        default=None,
        help="Path to Phase 1 output file (for Phase 2)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="outputs",
        help="Output directory (default: outputs)",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce verbosity",
    )

    args = parser.parse_args()
    verbose = not args.quiet

    if args.phase in ("architecture", "all"):
        from crews.architecture_crew import run_architecture_phase

        arch_result = run_architecture_phase(
            task_description=args.task,
            output_dir=args.output_dir,
            verbose=verbose,
        )

        if args.phase == "all":
            print("\n" + "=" * 60)
            print("HUMAN REVIEW CHECKPOINT")
            print("=" * 60)
            print("Review the architecture output above.")
            print("If satisfied, press Enter to proceed to Phase 2 (coding).")
            print("Type 'q' to quit and review offline.\n")

            user_input = input(">>> ").strip().lower()
            if user_input in ("q", "quit", "exit"):
                print("Exiting. Run Phase 2 later with:")
                print(f"  python main.py --phase coding --architecture {args.output_dir}/architecture_*.json")
                return

            # Proceed to Phase 2 with the architecture output
            import glob
            arch_files = sorted(glob.glob(f"{args.output_dir}/architecture_*.json"))
            if arch_files:
                args.architecture = arch_files[-1]
            else:
                print("ERROR: No architecture output found.")
                return

    if args.phase in ("coding", "all"):
        if not args.architecture:
            print("ERROR: --architecture file required for coding phase.")
            print("Run Phase 1 first: python main.py --phase architecture")
            sys.exit(1)

        if not Path(args.architecture).exists():
            print(f"ERROR: Architecture file not found: {args.architecture}")
            sys.exit(1)

        from crews.coding_crew import run_coding_phase

        run_coding_phase(
            architecture_file=args.architecture,
            output_dir=args.output_dir,
            verbose=verbose,
        )


if __name__ == "__main__":
    main()
