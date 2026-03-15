## UMI 16S rRNA Project Architecturer ./multi_agent

Automated workflow design and code generation for UMI-based 16S rRNA metatranscriptomic abundance analysis, powered by a multi-agent LLM system with CrewAI orchestration and direct API tool integration.

### Project Structure

This project consists of two main components:

1. **`./multi_agent`** -- Multi-agent LLM system for automated workflow architecture design and code generation
2. **`./16s_rRNA_workflow`** -- The actual bioinformatics pipeline implementation (Snakemake workflow + Python scripts)

**Workflow:**
```
Task Description → multi_agent (Phase 1: Architecture) → Human Review → multi_agent (Phase 2: Coding) → 16s_rRNA_workflow (Pipeline Execution)
```

The multi-agent module first designs the complete bioinformatics workflow (tools, parameters, steps), then generates the implementation code. The 16s_rRNA_workflow directory contains the actual pipeline that executes this design.

### Background

16S rRNA amplicon sequencing is the standard method for microbial community profiling. When combined with UMI (Unique Molecular Identifiers), PCR amplification bias can be corrected, improving clustering accuracy and abundance estimation -- particularly important in metatranscriptomics where transcript-level quantification captures active microbial populations.

Traditional tools (DADA2, Mothur, QIIME2) handle clustering and taxonomy assignment well, but integrating UMI deduplication into the workflow requires specialized tools (UMI-tools, UMI-nea) and careful parameter tuning. This project uses a multi-agent LLM system to automate the research, design, and implementation of such a pipeline.

The existing analysis workflow (`rna_16s.smk`) supports three methods: meta denovo assembly, reference alignment, and fragment denovo assembly. This agentic module extends it with UMI-aware clustering and abundance estimation.

**Keywords:** Multi-Agent Systems, CrewAI, UMI, 16S rRNA, Metatranscriptomics, Microbial Abundance, Grok, PubMed, Tavily

---

### Architecture

```mermaid
graph TD
    subgraph Phase1["Phase 1: Architecture Module"]
        R[Researcher Agent]
        A[Analyst Agent]
        V[Architecture Reviewer]
        
        R -->|tools, papers, benchmarks| A
        A -->|workflow design| V
        V -->|score < 7: feedback| A
        V -->|score >= 7: PASS| HRC
    end

    subgraph Tools["Direct API Tools"]
        T1[Tavily Web Search]
        T2[PubMed E-utilities]
        T3[Code Execution]
    end

    R -.->|search| T1
    R -.->|literature| T2
    V -.->|fact-check| T1

    HRC{Human Review Checkpoint}

    subgraph Phase2["Phase 2: Coding Module"]
        C[Coder Agent]
        CR[Code Reviewer]

        C -->|implementation| CR
        CR -->|score < 7: fix instructions| C
        CR -->|score >= 7: PASS| OUT
    end

    C -.->|syntax test| T3
    CR -.->|validation| T3

    HRC -->|approved| Phase2

    subgraph Config["Configuration"]
        CFG[config/agents.yaml]
        ENV[.env API keys]
        CFG -.-> Phase1
        CFG -.-> Phase2
        ENV -.-> Tools
    end

    subgraph LLM["LLM Providers (configurable per agent)"]
        G[Grok / xAI]
        DS[DeepSeek]
        OA[OpenAI]
        GM[Google Gemini]
    end

    Phase1 -.-> LLM
    Phase2 -.-> LLM

    OUT[Output: umi_abundance.py + Snakemake rules]

    subgraph Existing["Existing Pipeline"]
        SMK[rna_16s.smk]
        AR[align_ref.py]
        R16[rna_16s.py]
    end

    OUT -->|integrates with| Existing
```

The system operates in two phases with a human review checkpoint:

**Phase 1 -- Architecture Module** (Researcher -> Analyst -> Reviewer)
1. **Researcher Agent** searches Tavily and PubMed for latest tools/papers on UMI-based 16S clustering.
2. **Analyst Agent** designs a step-by-step bioinformatics workflow based on findings.
3. **Architecture Reviewer** scores the design (0-10) and triggers revision if below threshold.

**Human Review Checkpoint** -- User reviews the approved architecture before proceeding.

**Phase 2 -- Coding Module** (Coder -> code-Reviewer)
4. **Coder Agent** implements the approved workflow as Python code, integrating with existing `rna_16s.smk`.
5. **Code Reviewer** validates syntax, logic, edge cases, and integration. Iterates until quality threshold met.

Each agent's LLM provider is independently configurable (Grok, DeepSeek, OpenAI, Gemini) via `config/agents.yaml`.

---

### Results

#### Phase 1: Architecture Design

```bash
cd src
python main.py --phase architecture \
    --task "UMI-based 16S rRNA clustering for metatranscriptomic abundance"
```

- **Input:** Task description (natural language)
- **Output:** `outputs/architecture_YYYYMMDD_HHMMSS.md` -- structured workflow design with tool recommendations, per-step I/O specifications, and integration plan.

#### Phase 2: Code Generation

```bash
cd src
python main.py --phase coding \
    --architecture outputs/architecture_YYYYMMDD_HHMMSS.json
```

- **Input:** Approved architecture document
- **Output:** `outputs/coding_YYYYMMDD_HHMMSS.md` -- implementation code (umi_abundance.py, Snakemake rules, requirements)

#### Full Pipeline (with interactive checkpoint)

```bash
cd src
python main.py --phase all
```

Runs Phase 1, pauses for human review, then proceeds to Phase 2.

---

### Materials and Methods

#### Data Context

| Component | Description |
|-----------|-------------|
| Input data | UMI-tagged NGS reads (FASTQ), 16S rRNA amplicons |
| Existing pipeline | `rna_16s.smk` -- Snakemake workflow for meta denovo, align to ref, frag denovo |
| Reference | ZymoBIOMICS 16S standard community (8 bacterial species) |
| Abundance ground truth | Zymo theoretical composition for benchmarking |

#### Tools and Algorithms

| Component | Tool | Why this choice |
|-----------|------|-----------------|
| Agent orchestration | [CrewAI](https://github.com/crewai/crewai) | Role-based agents with built-in delegation, reflection loops, and episodic memory. Best fit for structured sequential tasks with iterative quality control |
| Web search | [Tavily](https://tavily.com/) | AI-synthesized web search with source attribution. Direct API call (not through CrewAI) for reliability |
| Literature search | [PubMed E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25500/) | Direct XML API to NCBI. Structured article metadata (PMID, abstract, authors) |
| Default LLM | [Grok](https://x.ai/) (xAI) | Strong reasoning, web-grounded, OpenAI-compatible API. Configurable per agent |
| UMI dedup (target) | [UMI-tools](https://github.com/CGATOxford/UMI-tools) | Standard for UMI extraction and deduplication in NGS |
| Clustering (target) | [DADA2](https://benjjneb.github.io/dada2/) | ASV-level resolution, well-benchmarked for 16S |
| Taxonomy (target) | [QIIME2](https://qiime2.org/) + SILVA | Comprehensive taxonomy assignment framework |

#### Multi-Agent Architecture

The hybrid architecture combines CrewAI for agent lifecycle management with direct HTTP API calls for tool integration:

- **CrewAI layer** -- Agent role/goal/backstory definitions, task sequencing, memory persistence, delegation control.
- **Direct API layer** -- Tavily and PubMed search functions bypass CrewAI's built-in tool system for more control over request formatting, error handling, and response parsing.
- **LLM abstraction** -- `config.py` provides a unified `call_llm()` function that dispatches to the correct provider based on per-agent configuration. This eliminates shared blind spots when using different LLMs for generation vs review.

#### Anti-Degradation Measures

| Strategy | Implementation |
|----------|----------------|
| Episodic memory | CrewAI built-in memory across tasks within a crew |
| Reviewer reflection loop | Architecture Reviewer and Code Reviewer trigger re-runs if quality score < 7.0 |
| Configurable LLM diversity | Different agents can use different LLM providers to reduce shared failure modes |
| Structured output format | Tasks specify `expected_output` to constrain agent responses |
| State summarization | Reviewer produces structured scores + specific feedback per iteration |

---

### Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Configure API keys -- copy `.env.example` to `.env`:
   ```
   GROK_API_KEY=xai-your-key
   TAVILY_API_KEY=tvly-your-key
   PUBMED_EMAIL=your.email@example.com
   ```

3. (Optional) Customize agent LLMs in `config/agents.yaml`.

---

### Project Structure

```
agentic/
├── config/
│   └── agents.yaml              # Agent roles, LLM config, tool settings
├── src/
│   ├── main.py                  # Entry point (--phase architecture|coding|all)
│   ├── config.py                # API key management, LLM dispatch
│   ├── tools/
│   │   ├── tavily_search.py     # Tavily web search (direct API)
│   │   └── pubmed_search.py     # PubMed E-utilities (direct API)
│   └── crews/
│       ├── architecture_crew.py # Phase 1: Researcher + Analyst + Reviewer
│       └── coding_crew.py       # Phase 2: Coder + code-Reviewer
├── outputs/                     # Generated architecture docs and code
├── docs/
│   └── flowchart.mmd            # Mermaid architecture diagram
├── llm_genetics_assistant/      # Reference project (phased variant curation)
├── immune-drift-zero/           # Reference project (immune trajectory monitoring)
├── swarm.py                     # Initial prototype (superseded by crews/)
├── plan.md                      # Design rationale and decisions
├── requirements.txt
├── .env.example
├── README.md
└── README_CN.md
```

---

### Discussion

#### Why Multi-Agent over Single-Agent

A single LLM call cannot reliably perform the full loop of literature search, workflow design, code generation, and quality review. Each sub-task requires different expertise, tool access, and evaluation criteria. The multi-agent approach:

- **Separates concerns** -- Researcher focuses on search quality, Analyst on design coherence, Reviewer on scientific rigor.
- **Enables iterative refinement** -- Reviewer feedback loops prevent first-pass errors from propagating.
- **Human-in-the-loop** -- The checkpoint between Phase 1 and Phase 2 prevents wasted compute on flawed architectures.

#### Why CrewAI over Swarm

| Dimension | CrewAI | OpenAI Swarm |
|-----------|--------|--------------|
| **Task structure** | Role-based sequential/hierarchical | Dynamic handoff, decentralized |
| **Reflection** | Built-in reviewer loop | Manual implementation |
| **Memory** | Episodic memory built-in | No built-in memory |
| **LLM flexibility** | Any provider (Grok, DeepSeek, OpenAI, Gemini) | OpenAI only |
| **Best fit** | Structured research-design-code-review chains | Exploratory, parallel micro-agents |
| **Production readiness** | Mature (45k+ GitHub stars, 2026) | Experimental |

This project's workflow is inherently sequential and role-structured (research -> design -> review -> code -> review). CrewAI's role-based agent model and built-in reflection loops are a natural fit. Swarm's decentralized handoff model is better suited for open-ended exploration or parallel database queries -- a potential future extension for the Researcher agent.

#### Ongoing Work

- [ ] End-to-end test with real UMI 16S FASTQ data
- [ ] Benchmark generated pipeline against manual DADA2+UMI-tools workflow
- [ ] Add RAG layer (FAISS) for persistent literature context across runs
- [ ] LangGraph migration for stateful checkpointing across sessions
- [ ] Parallel Researcher sub-agents (Swarm-style) for multi-database search

---

## 16S rRNA Pipeline ./src

A legacy 16S rRNA microbial diversity sequencing analysis project supporting three analysis methods. This core pipeline provides the foundation for the multi-agent extension in `./multi_agent`.

### Results and Impact

The pipeline enables microbial community profiling through three complementary approaches:

1. **Meta De Novo** -- Metagenome assembly using MetaSPAdes for species annotation via Kraken
2. **Align to Ref** -- Reference-based alignment against ZymoBIOMICS 16S standard community for species identification
3. **Frag De Novo** (core method) -- Fragment-based assembly leveraging stLFR co-barcodes

The Frag De Novo method is particularly powerful for stLFR (Single Tube Long Fragment read) data, where each DNA fragment carries a unique barcode. By grouping reads by barcode, the pipeline performs per-fragment assembly, enabling:
- Pseudo-long-read assembly from short reads
- Fragment-level coverage analysis
- Strain-resolved assembly for complex communities

### Materials and Methods

#### Input and Output

| Component | Description |
|-----------|-------------|
| Input | Paired-end FASTQ from `data/split_read.{1,2}.fq.gz` (via splitreads.smk) |
| Barcode source | stLFR co-barcodes in BAM file (BX:Z: tag) |
| Output (general) | QUAST assembly quality reports |
| Output (ZymoBIOMICS) | Abundance statistics comparing observed vs theoretical composition |

#### Analysis Workflow

**Method 1: Meta De Novo**
```
FASTQ → Kraken (taxonomy) → MetaSPAdes (assembly) → QUAST (evaluation)
```

**Method 2: Align to Ref**
```
FASTQ → BWA mem → SAMtools sort → idxstats → abundance calculation
Reference: ZymoBIOMICS 16S standard (8 bacterial species)
```

**Method 3: Frag De Novo** (main method)
```
BAM → group by BX:Z:barcode → filter 200-1000 reads/barcode →
bc2fq.py (extract FASTQ) → SPAdes (per-barcode assembly) →
merge contigs → QUAST + coverage analysis
```

#### Key Functions (rna_16s.py)

| Function | Purpose |
|----------|---------|
| `pct_denovoFrag_ref()` | Calculate fragment coverage vs 16S reference length |
| `coverage_bias()` | Visualize fragment coverage distribution on 16S reference |
| `per_base_density()` | Generate per-base coverage density plots |
| `merge_exon_ref()` | Merge multiple contigs into single sequence |

#### Tools and Algorithms

| Component | Tool | Rationale |
|-----------|------|-----------|
| Assembler | [SPAdes](https://github.com/ablab/spades) | Versatile assembler supporting multiple modes (meta, rna, plasmid) |
| Alignment | [BWA](http://bio-bwa.sourceforge.net/) | Fast short-read aligner for reference mapping |
| Taxonomy | [Kraken](https://ccb.jhu.edu/software/kraken/) | k-mer based taxonomic classification |
| Assembly QC | [QUAST](https://quast.sourceforge.net/) | Comprehensive assembly quality metrics |
| Reference | ZymoBIOMICS 16S | Standard mock community (8 species) with known composition |

#### ZymoBIOMICS Standard Species

| Species | 16S Length (bp) |
|---------|-----------------|
| Bacillus subtilis | 1558 |
| Enterococcus faecalis | 1562 |
| Escherichia coli | 1542 |
| Lactobacillus fermentum | 1568-1578 |
| Listeria monocytogenes | 1552 |
| Pseudomonas aeruginosa | 1526 |
| Salmonella enterica | 1534 |
| Staphylococcus aureus | 1556 |

#### Frag De Novo Algorithm

1. **Barcode grouping** -- Extract reads from BAM by BX:Z: barcode
2. **Quality filtering** -- Select barcodes with 200-1000 reads (avoid low-coverage or PCR duplicates)
3. **Per-barcode assembly** -- Run SPAdes on each barcode's reads
4. **Contig selection** -- Keep longest contig per barcode (contigs_max.fasta)
5. **Reference alignment** -- Align contigs to ZymoBIOMICS 16S reference via minimap2
6. **Coverage calculation** -- For each fragment, compute: `frag_length / ref_16S_length`
7. **Abundance estimation** -- Compare observed coverage to theoretical Zymo composition

### Discussion

**Strengths:**
- Fragment-level assembly preserves long-range information lost in standard 16S amplicon sequencing
- Per-barcode assembly enables strain-resolved analysis in complex communities
- ZymoBIOMICS integration provides ground truth for benchmarking

**Limitations:**
- Requires stLFR data with co-barcodes (not standard 16S FASTQ)
- Assembly quality depends on per-barcode read depth
- No UMI deduplication (PCR bias correction)

**To-Do:**
- Integrate UMI deduplication for improved abundance accuracy
- Add DADA2-style denoising for ASV-level resolution
- Benchmark against mock community ground truth

---


### References

1. [CrewAI](https://github.com/crewai/crewai) -- Multi-agent orchestration framework
2. [UMI-tools](https://github.com/CGATOxford/UMI-tools) -- UMI extraction and deduplication
3. [DADA2](https://benjjneb.github.io/dada2/) -- High-resolution amplicon denoising
4. [QIIME2](https://qiime2.org/) -- Microbiome bioinformatics platform
5. [Tavily](https://tavily.com/) -- Web search API with AI synthesis
6. [PubMed E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25500/) -- NCBI literature API
7. [Grok](https://x.ai/) -- xAI large language model
8. [ZymoBIOMICS](https://www.zymoresearch.com/collections/zymobiomics-microbial-community-standards) -- Microbial community standard
9. [mclUMI](https://doi.org/10.1093/bioinformatics/btaf068) -- Markov clustering for UMI deduplication (2025)
10. [SPAdes](https://github.com/ablab/spades) -- De novo genome assembler
