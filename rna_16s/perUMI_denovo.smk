# perUMI_denovo.smk — Per-UMI de novo assembly for full-length 16S rRNA (PE150)
#
# BX tag (15bp) in FASTQ header = UMI = barcode (same as frag_denovo, different assembler)
#
# Why MEGAHIT over SPAdes:
#   - SPAdes --isolate: designed for whole-genome isolates, over-corrects amplicon data
#   - MEGAHIT: succinct De Bruijn Graph, handles low-coverage (~10x) better,
#     faster startup, lower memory — ideal for 50 reads / 1500bp per UMI
#
# Pipeline:
#   fastp trim → group by BX tag → MEGAHIT per UMI (parallel) → filter → merge → QUAST
#
# Standalone:  snakemake -s perUMI_denovo.smk per_umi_denovo_all -j 32
# As module:   included from rna_16s.smk when mode = 'per_umi_denovo'

import os
from pathlib import Path

configfile: "config.yaml"

# ============================================================================
# Configuration
# ============================================================================
SAMPLE_ID     = config['samples'].get('id', 'data')
REF_16S       = config['params'].get('ref_fa_other', '')
QUAST         = config['frag_de_novo'].get('quast_dir', 'quast/quast.py')
THREADS_QUAST = config['threads'].get('quast', 4)
SCRIPT_DIR    = str(Path(workflow.basedir))

# Per-UMI denovo config
PER_UMI_CFG       = config.get('per_umi_denovo', {})
MIN_READS_UMI     = PER_UMI_CFG.get('min_reads_per_umi', 5)
MAX_READS_UMI     = PER_UMI_CFG.get('max_reads_per_umi', 500)
MEGAHIT_K         = PER_UMI_CFG.get('k_list', '21,41,61,81')
THREADS_PER_UMI   = PER_UMI_CFG.get('threads_per_umi', 4)
THREADS_TOTAL     = PER_UMI_CFG.get('threads_total', 32)
CONSENSUS_MIN_LEN = PER_UMI_CFG.get('consensus_min_length', 1400)
BX_PATTERN        = PER_UMI_CFG.get('bx_pattern', r'BX:Z:(\S+)')
MEGAHIT           = PER_UMI_CFG.get('megahit', 'megahit')

# Output prefix
OUT = "rna_16s/per_umi_denovo"


# ============================================================================
# Target rule
# ============================================================================
rule per_umi_denovo_all:
    input:
        f"{OUT}/all_umi_contigs.fasta",
        f"rna_16s/quast/per_umi_denovo/report.txt"


# ============================================================================
# Step 1: Adapter trimming + QC (fastp, PE mode)
# ============================================================================
rule per_umi_trim:
    input:
        r1="data/split_read.1.fq.gz",
        r2="data/split_read.2.fq.gz"
    output:
        r1=f"{OUT}/trimmed/R1.fq.gz",
        r2=f"{OUT}/trimmed/R2.fq.gz",
        json=f"{OUT}/trimmed/fastp.json",
        html=f"{OUT}/trimmed/fastp.html"
    threads: 12
    log: f"{OUT}/logs/fastp.log"
    shell:
        """
        mkdir -p $(dirname {output.r1})
        fastp -i {input.r1} -I {input.r2} \
            -o {output.r1} -O {output.r2} \
            -j {output.json} -h {output.html} \
            --thread {threads} --detect_adapter_for_pe \
            2>{log}
        """


# ============================================================================
# Step 2: Group reads by UMI (BX tag in FASTQ header)
#   Outputs per-UMI FASTQ files + umi_list.txt
# ============================================================================
rule group_by_umi:
    input:
        r1=f"{OUT}/trimmed/R1.fq.gz",
        r2=f"{OUT}/trimmed/R2.fq.gz"
    output:
        umi_dir=directory(f"{OUT}/per_umi_fq"),
        umi_list=f"{OUT}/per_umi_fq/umi_list.txt"
    params:
        script=SCRIPT_DIR + "/group_reads_by_umi.py",
        min_reads=MIN_READS_UMI,
        max_reads=MAX_READS_UMI,
        bx_pattern=BX_PATTERN
    log: f"{OUT}/logs/group_by_umi.log"
    shell:
        """
        python3 {params.script} \
            --r1 {input.r1} --r2 {input.r2} \
            --outdir {output.umi_dir} \
            --min_reads {params.min_reads} \
            --max_reads {params.max_reads} \
            --bx_pattern '{params.bx_pattern}' \
            2>{log}
        """


# ============================================================================
# Step 3: MEGAHIT de novo assembly per UMI (all UMIs, internally parallel)
#
#   per_umi_megahit_consensus.py:
#     - Reads per-UMI FASTQs from umi_dir
#     - Runs MEGAHIT per UMI with ThreadPoolExecutor
#     - Extracts longest contig per UMI
#     - Filters by consensus_min_length (1400bp for full-length 16S)
#     - Outputs merged FASTA
#
#   High I/O optimization:
#     - Parallel MEGAHIT: threads_total / threads_per_umi concurrent runs
#     - MEGAHIT intermediate files cleaned after each UMI
#     - resources controls HPC/Slurm allocation
# ============================================================================
rule per_umi_megahit:
    input:
        umi_dir=f"{OUT}/per_umi_fq",
        umi_list=f"{OUT}/per_umi_fq/umi_list.txt"
    output:
        contigs=f"{OUT}/all_umi_contigs.fasta"
    params:
        script=SCRIPT_DIR + "/per_umi_megahit_consensus.py",
        outdir=f"{OUT}/asm",
        min_reads=MIN_READS_UMI,
        min_length=CONSENSUS_MIN_LEN,
        k_list=MEGAHIT_K,
        threads_per_umi=THREADS_PER_UMI,
        megahit=MEGAHIT
    threads: THREADS_TOTAL
    resources:
        mem_mb=64000,
        disk_mb=100000
    log: f"{OUT}/logs/megahit_all.log"
    shell:
        """
        python3 {params.script} \
            --umi_dir {input.umi_dir} \
            --umi_list {input.umi_list} \
            --outdir {params.outdir} \
            --output {output.contigs} \
            --min_reads {params.min_reads} \
            --min_length {params.min_length} \
            --k_list {params.k_list} \
            --threads {threads} \
            --threads_per_umi {params.threads_per_umi} \
            --megahit {params.megahit} \
            2>{log}
        """


# ============================================================================
# Step 4: QUAST evaluation against reference
# ============================================================================
rule quast_per_umi_denovo:
    input:
        f"{OUT}/all_umi_contigs.fasta"
    output:
        report="rna_16s/quast/per_umi_denovo/report.txt"
    params:
        ref=REF_16S,
        out_dir="rna_16s/quast/per_umi_denovo",
        quast=QUAST,
        threads=THREADS_QUAST
    shell:
        """
        {params.quast} {input} -o {params.out_dir} -r {params.ref} \
            --min-contig 100 --no-snps --threads {params.threads} --space-efficient
        """


# ============================================================================
# Step 5: Zymo abundance comparison (control samples)
# ============================================================================
rule abundance_per_umi_denovo:
    input:
        quast_report="rna_16s/quast/per_umi_denovo/report.txt"
    output:
        "rna_16s/abundance_per_umi_denovo.txt"
    params:
        python="python3",
        script=SCRIPT_DIR + '/rna_16s.py',
        coords_dir="rna_16s/quast/per_umi_denovo"
    shell:
        """
        {params.python} {params.script} --module metrics_ref_zymo \
            --outdir {params.coords_dir} > {output}
        """
