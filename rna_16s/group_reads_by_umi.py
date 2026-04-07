#!/usr/bin/env python3
"""Group paired-end FASTQ reads by UMI (BX:Z: tag in FASTQ header).

Reads R1/R2 FASTQ files, extracts BX:Z: tag from headers,
groups read pairs by UMI, filters by read count, and writes
per-UMI FASTQ files.

Usage:
    python group_reads_by_umi.py \
        --r1 trimmed_R1.fq.gz --r2 trimmed_R2.fq.gz \
        --outdir per_umi_fq/ --min_reads 10 --max_reads 500

Output:
    {outdir}/{umi}_R1.fastq.gz    per-UMI R1
    {outdir}/{umi}_R2.fastq.gz    per-UMI R2
    {outdir}/umi_list.txt          umi<TAB>read_count
    {outdir}/umi_stats.txt         summary statistics
"""

import argparse
import gzip
import os
import re
import sys
from collections import defaultdict


def parse_bx_tag(header, pattern):
    """Extract UMI/barcode from FASTQ header."""
    match = re.search(pattern, header)
    return match.group(1) if match else None


def read_fastq_record(fh):
    """Read one FASTQ record (4 lines). Returns None at EOF."""
    header = fh.readline()
    if not header:
        return None
    seq = fh.readline()
    plus = fh.readline()
    qual = fh.readline()
    return (header, seq, plus, qual)


def main():
    parser = argparse.ArgumentParser(
        description="Group PE FASTQ reads by UMI (BX tag in header)")
    parser.add_argument('--r1', required=True, help="R1 FASTQ (gzipped)")
    parser.add_argument('--r2', required=True, help="R2 FASTQ (gzipped)")
    parser.add_argument('--outdir', required=True, help="Output directory")
    parser.add_argument('--min_reads', type=int, default=10,
                        help="Min read pairs per UMI group (default: 10)")
    parser.add_argument('--max_reads', type=int, default=500,
                        help="Max read pairs per UMI group (default: 500)")
    parser.add_argument('--bx_pattern', default=r'BX:Z:(\S+)',
                        help="Regex to extract UMI from header (default: BX:Z:(\\S+))")
    args = parser.parse_args()

    os.makedirs(args.outdir, exist_ok=True)

    # Single-pass: group reads by UMI in memory
    # For 16S amplicon data this is feasible (typically < a few million reads)
    umi_reads = defaultdict(lambda: ([], []))
    total_reads = 0
    no_bx_count = 0

    print("Reading FASTQ files and grouping by UMI ...", file=sys.stderr)
    with gzip.open(args.r1, 'rt') as f1, gzip.open(args.r2, 'rt') as f2:
        while True:
            rec1 = read_fastq_record(f1)
            rec2 = read_fastq_record(f2)
            if rec1 is None:
                break
            total_reads += 1
            bx = parse_bx_tag(rec1[0], args.bx_pattern)
            if bx is None:
                no_bx_count += 1
                continue
            r1_list, r2_list = umi_reads[bx]
            r1_list.append(rec1)
            r2_list.append(rec2)

    # Filter by read count and write per-UMI FASTQs
    valid_umis = []
    print("Writing per-UMI FASTQ files ...", file=sys.stderr)
    for umi in sorted(umi_reads.keys()):
        r1_recs, r2_recs = umi_reads[umi]
        n = len(r1_recs)
        if n < args.min_reads or n > args.max_reads:
            continue
        valid_umis.append((umi, n))
        r1_path = os.path.join(args.outdir, f'{umi}_R1.fastq.gz')
        r2_path = os.path.join(args.outdir, f'{umi}_R2.fastq.gz')
        with gzip.open(r1_path, 'wt', compresslevel=4) as out1:
            for rec in r1_recs:
                out1.writelines(rec)
        with gzip.open(r2_path, 'wt', compresslevel=4) as out2:
            for rec in r2_recs:
                out2.writelines(rec)

    # Write UMI list (consumed by snakemake checkpoint)
    umi_list_path = os.path.join(args.outdir, 'umi_list.txt')
    with open(umi_list_path, 'w') as f:
        for umi, count in valid_umis:
            f.write(f'{umi}\t{count}\n')

    # Write stats summary
    stats_path = os.path.join(args.outdir, 'umi_stats.txt')
    with open(stats_path, 'w') as f:
        f.write(f'total_read_pairs\t{total_reads}\n')
        f.write(f'reads_without_bx\t{no_bx_count}\n')
        f.write(f'total_umis\t{len(umi_reads)}\n')
        f.write(f'valid_umis\t{len(valid_umis)}\n')
        f.write(f'min_reads_filter\t{args.min_reads}\n')
        f.write(f'max_reads_filter\t{args.max_reads}\n')
        if valid_umis:
            counts = [c for _, c in valid_umis]
            f.write(f'median_reads_per_umi\t{sorted(counts)[len(counts)//2]}\n')

    print(f"Total read pairs: {total_reads}", file=sys.stderr)
    print(f"Reads without BX tag: {no_bx_count}", file=sys.stderr)
    print(f"Total UMIs found: {len(umi_reads)}", file=sys.stderr)
    print(f"Valid UMIs ({args.min_reads}-{args.max_reads} reads): {len(valid_umis)}",
          file=sys.stderr)


if __name__ == '__main__':
    main()
