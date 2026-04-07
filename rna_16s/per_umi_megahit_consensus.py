#!/usr/bin/env python3
"""Per-UMI de novo assembly using MEGAHIT for full-length 16S rRNA (PE150).

Reads per-UMI FASTQ files (grouped by BX tag), runs MEGAHIT on each UMI group,
extracts the longest contig, filters by length, and outputs a merged FASTA.

Usage:
    python per_umi_megahit_consensus.py \
        --umi_dir per_umi_fq/ \
        --umi_list per_umi_fq/umi_list.txt \
        --outdir per_umi_asm/ \
        --output all_umi_contigs.fasta \
        --min_reads 5 --min_length 1400 \
        --k_list 21,41,61,81 --threads 32 --threads_per_umi 4
"""

import argparse
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def get_max_contig(fasta_path):
    """Return (header, sequence) of the longest contig in a FASTA file."""
    best_header, best_seq = None, ""
    header, seq_parts = None, []
    with open(fasta_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith('>'):
                if header and len(''.join(seq_parts)) > len(best_seq):
                    best_header = header
                    best_seq = ''.join(seq_parts)
                header = line
                seq_parts = []
            else:
                seq_parts.append(line)
    if header and len(''.join(seq_parts)) > len(best_seq):
        best_header = header
        best_seq = ''.join(seq_parts)
    return best_header, best_seq


def run_megahit_one_umi(umi, n_reads, umi_dir, outdir, k_list, threads_per_umi, min_length, megahit_bin="megahit"):
    """Run MEGAHIT for a single UMI group. Returns (umi, header, seq) or (umi, None, None)."""
    r1 = os.path.join(umi_dir, f"{umi}_R1.fastq.gz")
    r2 = os.path.join(umi_dir, f"{umi}_R2.fastq.gz")
    asm_dir = os.path.join(outdir, f"megahit_{umi}")

    # Skip if input files missing
    if not os.path.exists(r1) or not os.path.exists(r2):
        return umi, None, None, f"SKIP: missing FASTQ for {umi}"

    # Remove previous run if exists (MEGAHIT won't overwrite)
    if os.path.exists(asm_dir):
        subprocess.run(["rm", "-rf", asm_dir], check=False)

    # Run MEGAHIT
    cmd = [
        megahit_bin,
        "-1", r1, "-2", r2,
        "--out-dir", asm_dir,
        "--k-list", k_list,
        "-t", str(threads_per_umi),
        "--min-contig-len", "200",
        "--no-mercy",           # stricter, avoids chimeric contigs at low cov
        "--min-count", "2",     # k-mer min multiplicity
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)

    contig_file = os.path.join(asm_dir, "final.contigs.fa")
    if result.returncode != 0 or not os.path.exists(contig_file):
        # Cleanup on failure
        subprocess.run(["rm", "-rf", asm_dir], check=False)
        return umi, None, None, f"FAIL: {umi} (returncode={result.returncode})"

    # Get longest contig
    header, seq = get_max_contig(contig_file)

    # Cleanup MEGAHIT intermediate files (keep final.contigs.fa only)
    for item in Path(asm_dir).iterdir():
        if item.name != "final.contigs.fa":
            if item.is_dir():
                subprocess.run(["rm", "-rf", str(item)], check=False)
            else:
                item.unlink(missing_ok=True)

    if header is None or len(seq) < min_length:
        status = f"SHORT: {umi} len={len(seq) if seq else 0} < {min_length}"
        return umi, None, None, status

    # Rename header to include UMI
    new_header = f">{umi} length={len(seq)}"
    return umi, new_header, seq, f"OK: {umi} len={len(seq)} reads={n_reads}"


def main():
    parser = argparse.ArgumentParser(
        description="Per-UMI MEGAHIT assembly for full-length 16S")
    parser.add_argument('--umi_dir', required=True,
                        help="Directory with per-UMI FASTQ files")
    parser.add_argument('--umi_list', required=True,
                        help="TSV: umi<TAB>read_count")
    parser.add_argument('--outdir', required=True,
                        help="Output directory for MEGAHIT runs")
    parser.add_argument('--output', required=True,
                        help="Output merged FASTA")
    parser.add_argument('--min_reads', type=int, default=5,
                        help="Min reads per UMI (default: 5)")
    parser.add_argument('--min_length', type=int, default=1400,
                        help="Min contig length for full-length 16S (default: 1400)")
    parser.add_argument('--k_list', default="21,41,61,81",
                        help="MEGAHIT k-mer list (default: 21,41,61,81)")
    parser.add_argument('--threads', type=int, default=32,
                        help="Total threads (default: 32)")
    parser.add_argument('--threads_per_umi', type=int, default=4,
                        help="Threads per MEGAHIT run (default: 4)")
    parser.add_argument('--megahit', default="megahit",
                        help="Path to megahit binary (default: megahit)")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    # Read UMI list
    umis = []
    with open(args.umi_list) as f:
        for line in f:
            parts = line.strip().split('\t')
            if len(parts) >= 2:
                umi, count = parts[0], int(parts[1])
                if count >= args.min_reads:
                    umis.append((umi, count))

    print(f"UMIs to assemble: {len(umis)}", file=sys.stderr)

    # Parallel MEGAHIT runs
    max_workers = max(1, args.threads // args.threads_per_umi)
    results = []
    n_ok, n_fail, n_short = 0, 0, 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                run_megahit_one_umi,
                umi, n_reads, args.umi_dir, args.outdir,
                args.k_list, args.threads_per_umi, args.min_length,
                args.megahit
            ): umi
            for umi, n_reads in umis
        }
        for future in as_completed(futures):
            umi, header, seq, status = future.result()
            print(status, file=sys.stderr)
            if header is not None:
                results.append((header, seq))
                n_ok += 1
            elif "SHORT" in status:
                n_short += 1
            else:
                n_fail += 1

    # Write merged output
    with open(args.output, 'w') as f:
        for header, seq in sorted(results, key=lambda x: x[0]):
            f.write(f"{header}\n{seq}\n")

    # Write stats
    stats_path = os.path.join(args.outdir, "assembly_stats.txt")
    with open(stats_path, 'w') as f:
        f.write(f"total_umis\t{len(umis)}\n")
        f.write(f"assembled_ok\t{n_ok}\n")
        f.write(f"failed_assembly\t{n_fail}\n")
        f.write(f"too_short\t{n_short}\n")
        f.write(f"min_length_filter\t{args.min_length}\n")

    print(f"\nDone: {n_ok} full-length consensus, "
          f"{n_fail} failed, {n_short} too short", file=sys.stderr)


if __name__ == '__main__':
    main()
