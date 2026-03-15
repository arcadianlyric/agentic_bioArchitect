
## UMI 16S rRNA 架构

本项目包含两个模块：
1. multi_agent_architecturer LLM 规划器，用于自动化工作流架构设计和代码生成
2. 16s_rRNA_workflow：由 architecturer 模块设计的实际生物信息学流水线实现（Snakemake 工作流 + Python 脚本）

## 1. 将 multi_agent 架构应用于 UMI 16S rRNA

基于 UMI 的 16S rRNA 宏转录组丰度分析的自动化工作流设计和代码生成，采用 CrewAI 编排的多代理 LLM 系统和直接 API 工具集成。

该流水线通过三种互补方法实现微生物群落分析：

1. **Meta De Novo** -- 使用 MetaSPAdes 进行宏基因组组装，通过 Kraken 进行物种注释
2. **Align to Ref** -- 将测序 reads 比对到 ZymoBIOMICS 16S 标准菌群进行物种鉴定
3. **Frag De Novo**（核心方法）-- 利用 stLFR 共条码进行基于 Fragment 的组装

Frag De Novo 方法对 stLFR（单管长片段读取）数据特别有效，每个 DNA 片段携带唯一条码。通过按条码分组 reads，流水线执行逐片段组装，实现：
- 从短 reads 进行伪长 reads 组装
- 片段级别覆盖度分析
- 复杂群落的株级别组装

### 材料与方法

#### 输入与输出

| 组件 | 描述 |
|------|------|
| 输入 | 来自 `data/split_read.{1,2}.fq.gz` 的双端 FASTQ（通过 splitreads.smk） |
| 条码来源 | BAM 文件中的 stLFR 共条码（BX:Z: 标签） |
| 输出（常规） | QUAST 组装质量报告 |
| 输出（ZymoBIOMICS） | 丰度统计，比较观测值与理论组成 |

#### 分析工作流

**方法 1: Meta De Novo**
```
FASTQ → Kraken（分类）→ MetaSPAdes（组装）→ QUAST（评估）
```

**方法 2: Align to Ref**
```
FASTQ → BWA mem → SAMtools sort → idxstats → 丰度计算
参考序列：ZymoBIOMICS 16S 标准菌群（8 种细菌）
```

**方法 3: Frag De Novo**（主要方法）
```
BAM → 按 BX:Z:barcode 分组 → 筛选 200-1000 reads/barcode →
bc2fq.py（提取 FASTQ）→ SPAdes（逐条码组装）→
合并 contigs → QUAST + 覆盖度分析
```

#### 关键函数 (rna_16s.py)

| 函数 | 用途 |
|------|------|
| `pct_denovoFrag_ref()` | 计算片段覆盖度与 16S 参考长度的比值 |
| `coverage_bias()` | 可视化片段在 16S 参考上的覆盖分布 |
| `per_base_density()` | 生成逐碱基覆盖密度图 |
| `merge_exon_ref()` | 将多个 contigs 合并为单条序列 |

#### 工具与算法

| 组件 | 工具 | 选择理由 |
|------|------|----------|
| 组装器 | [SPAdes](https://github.com/ablab/spades) | 多功能组装器，支持多种模式（meta、rna、plasmid） |
| 比对 | [BWA](http://bio-bwa.sourceforge.net/) | 快速短 reads 比对工具 |
| 分类 | [Kraken](https://ccb.jhu.edu/software/kraken/) | 基于 k-mer 的分类方法 |
| 组装质控 | [QUAST](https://quast.sourceforge.net/) | 全面的组装质量指标 |
| 参考 | ZymoBIOMICS 16S | 标准 mock 菌群（8 种），组成已知 |

#### ZymoBIOMICS 标准菌种

| 菌种 | 16S 长度 (bp) |
|------|---------------|
| Bacillus subtilis | 1558 |
| Enterococcus faecalis | 1562 |
| Escherichia coli | 1542 |
| Lactobacillus fermentum | 1568-1578 |
| Listeria monocytogenes | 1552 |
| Pseudomonas aeruginosa | 1526 |
| Salmonella enterica | 1534 |
| Staphylococcus aureus | 1556 |

#### Frag De Novo 算法

1. **条码分组** -- 从 BAM 中按 BX:Z: barcode 提取 reads
2. **质量筛选** -- 选择 200-1000 reads/barcode 的条码（避免低覆盖或 PCR 重复）
3. **逐条码组装** -- 对每个条码的 reads 运行 SPAdes
4. **Contig 选取** -- 保留每个条码的最长 contig（contigs_max.fasta）
5. **参考比对** -- 通过 minimap2 将 contigs 比对到 ZymoBIOMICS 16S 参考
6. **覆盖度计算** -- 对每个片段计算：`frag_length / ref_16S_length`
7. **丰度估计** -- 将观测覆盖度与理论 Zymo 组成进行比较

### 讨论

**优势：**
- 片段级别组装保留了标准 16S 扩增子测序中丢失的长程信息
- 逐条码组装实现复杂群落的株级别分析
- ZymoBIOMICS 集成提供基准测试的真值

**局限：**
- 需要带共条码的 stLFR 数据（非标准 16S FASTQ）
- 组装质量取决于逐条码的 reads 深度
- 无 UMI 去重（PCR 偏差校正）

**待办：**
- 集成 UMI 去重以提高丰度精度
- 添加 DADA2 风格的去噪以实现 ASV 级别分辨率
- 基于 mock 菌群真值进行基准测试

---

## UMI 16S rRNA 多代理分析流水线 ./multi_agent

基于多代理 LLM 系统，自动化 UMI 16S rRNA 宏转录组丰度分析的工作流设计与代码生成。采用 CrewAI 编排框架与直接 API 工具集成的混合架构。

### 背景

16S rRNA 扩增子测序是微生物群落分析的标准方法。结合 UMI（唯一分子标识符）可以校正 PCR 扩增偏差，提高聚类准确性和丰度估计精度。这在宏转录组学中尤为重要，因为转录本水平的定量能捕捉活跃的微生物群体。

传统工具（DADA2、Mothur、QIIME2）可以处理聚类和分类注释，但将 UMI 去重整合到工作流中需要专用工具（UMI-tools、UMI-nea）和精细的参数调优。本项目使用多代理 LLM 系统自动化完成这一流水线的研究、设计和实现。

现有分析工作流（`src/rna_16s.smk`）支持三种方法：meta denovo 组装、参考序列比对、片段 denovo 组装。本 agentic 模块在此基础上扩展 UMI 感知的聚类和丰度估计能力。

**关键词：** 多代理系统、CrewAI、UMI、16S rRNA、宏转录组学、微生物丰度、Grok、PubMed、Tavily

---

### 架构

![flowchart](docs/flowchart.mmd)

系统分为两个阶段，中间设有人工审阅检查点：

**阶段 1 -- 架构模块**（Researcher -> Analyst -> Reviewer）
1. **Researcher Agent** 通过 Tavily 和 PubMed 搜索 UMI 16S 聚类的最新工具和论文。
2. **Analyst Agent** 基于搜索结果设计逐步的生物信息学工作流。
3. **Architecture Reviewer** 对设计打分（0-10），低于阈值则触发修订迭代。

**人工审阅检查点** -- 用户审阅通过的架构方案后再进入下一阶段。

**阶段 2 -- 编码模块**（Coder -> code-Reviewer）
4. **Coder Agent** 将已批准的工作流实现为 Python 代码，与现有 `rna_16s.smk` 集成。
5. **Code Reviewer** 验证语法、逻辑、边界情况和集成兼容性，迭代直到质量达标。

每个 Agent 的 LLM 提供商可通过 `config/agents.yaml` 独立配置（Grok、DeepSeek、OpenAI、Gemini）。

---

### 结果

#### 阶段 1：架构设计

```bash
cd src
python main.py --phase architecture \
    --task "UMI-based 16S rRNA clustering for metatranscriptomic abundance"
```

- **输入：** 任务描述（自然语言）
- **输出：** `outputs/architecture_YYYYMMDD_HHMMSS.md` -- 结构化的工作流设计，包含工具推荐、逐步 I/O 规范和集成方案。

#### 阶段 2：代码生成

```bash
cd src
python main.py --phase coding \
    --architecture outputs/architecture_YYYYMMDD_HHMMSS.json
```

- **输入：** 已批准的架构文档
- **输出：** `outputs/coding_YYYYMMDD_HHMMSS.md` -- 实现代码（umi_abundance.py、Snakemake 规则、依赖清单）

#### 完整流水线（含交互式暂停）

```bash
cd src
python main.py --phase all
```

运行阶段 1，暂停等待人工审阅，然后进入阶段 2。

---

### 材料与方法

#### 数据背景

| 组件 | 描述 |
|------|------|
| 输入数据 | UMI 标记的 NGS reads（FASTQ），16S rRNA 扩增子 |
| 现有流水线 | `rna_16s.smk` -- Snakemake 工作流，支持 meta denovo、参考比对、片段 denovo |
| 参考序列 | ZymoBIOMICS 16S 标准菌群（8 种细菌） |
| 丰度基准 | Zymo 理论组成，用于基准测试 |

#### 工具与算法

| 组件 | 工具 | 选择理由 |
|------|------|----------|
| Agent 编排 | [CrewAI](https://github.com/crewai/crewai) | 基于角色的 Agent 定义，内置 delegation、反思循环和情景记忆。最适合结构化顺序任务的迭代质量控制 |
| Web 搜索 | [Tavily](https://tavily.com/) | AI 综合的网络搜索，带来源归属。直接 API 调用（不经过 CrewAI）以确保可靠性 |
| 文献搜索 | [PubMed E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25500/) | 直接 XML API 访问 NCBI，结构化的文章元数据（PMID、摘要、作者） |
| 默认 LLM | [Grok](https://x.ai/)（xAI） | 强推理能力，网络事实根基，OpenAI 兼容 API。可按 Agent 配置 |
| UMI 去重（目标） | [UMI-tools](https://github.com/CGATOxford/UMI-tools) | NGS UMI 提取和去重的标准工具 |
| 聚类（目标） | [DADA2](https://benjjneb.github.io/dada2/) | ASV 级分辨率，16S 领域充分基准测试 |
| 分类注释（目标） | [QIIME2](https://qiime2.org/) + SILVA | 综合性分类注释框架 |

#### 多代理架构

混合架构将 CrewAI 用于 Agent 生命周期管理，直接 HTTP API 调用用于工具集成：

- **CrewAI 层** -- Agent 角色/目标/背景定义、任务排序、记忆持久化、delegation 控制。
- **直接 API 层** -- Tavily 和 PubMed 搜索函数绕过 CrewAI 内置工具系统，对请求格式、错误处理和响应解析有更多控制。
- **LLM 抽象** -- `config.py` 提供统一的 `call_llm()` 函数，根据每个 Agent 的配置分发到正确的提供商。当生成和审阅使用不同 LLM 时，可消除共享盲点。

#### 防降智策略

| 策略 | 实现方式 |
|------|----------|
| 情景记忆 | CrewAI 内置的跨任务记忆 |
| Reviewer 反思循环 | Architecture Reviewer 和 Code Reviewer 在质量评分 < 7.0 时触发重新运行 |
| 可配置 LLM 多样性 | 不同 Agent 可使用不同 LLM 提供商，降低共享故障模式 |
| 结构化输出格式 | Task 指定 `expected_output` 约束 Agent 响应 |
| 状态总结 | Reviewer 每次迭代产出结构化评分和具体反馈 |

---

### 安装

1. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

2. 配置 API 密钥 -- 复制 `.env.example` 为 `.env`：
   ```
   GROK_API_KEY=xai-your-key
   TAVILY_API_KEY=tvly-your-key
   PUBMED_EMAIL=your.email@example.com
   ```

3. （可选）在 `config/agents.yaml` 中自定义各 Agent 的 LLM。

---

### 项目结构

```
agentic/
├── config/
│   └── agents.yaml              # Agent 角色、LLM 配置、工具设置
├── src/
│   ├── main.py                  # 入口（--phase architecture|coding|all）
│   ├── config.py                # API 密钥管理、LLM 分发
│   ├── tools/
│   │   ├── tavily_search.py     # Tavily 网络搜索（直接 API）
│   │   └── pubmed_search.py     # PubMed E-utilities（直接 API）
│   └── crews/
│       ├── architecture_crew.py # 阶段 1：Researcher + Analyst + Reviewer
│       └── coding_crew.py       # 阶段 2：Coder + code-Reviewer
├── outputs/                     # 生成的架构文档和代码
├── docs/
│   └── flowchart.mmd            # Mermaid 架构图
├── llm_genetics_assistant/      # 参考项目（变异注释策展）
├── immune-drift-zero/           # 参考项目（免疫轨迹监测）
├── swarm.py                     # 初始原型（已被 crews/ 取代）
├── plan.md                      # 设计决策文档
├── requirements.txt
├── .env.example
├── README.md
└── README_CN.md
```

---

### 讨论

#### 为什么选择多代理而非单代理

单次 LLM 调用无法可靠地完成文献搜索、工作流设计、代码生成和质量审阅的完整循环。每个子任务需要不同的专业知识、工具访问和评估标准。多代理方案：

- **关注点分离** -- Researcher 专注搜索质量，Analyst 专注设计连贯性，Reviewer 专注科学严谨性。
- **迭代改进** -- Reviewer 反馈循环防止初始错误传播。
- **人在回路中** -- 阶段 1 和阶段 2 之间的检查点防止在有缺陷的架构上浪费算力。

#### 为什么选择 CrewAI 而非 Swarm

| 维度 | CrewAI | OpenAI Swarm |
|------|--------|--------------|
| **任务结构** | 基于角色的顺序/层级执行 | 动态 handoff，去中心化 |
| **反思机制** | 内置 Reviewer 循环 | 需手动实现 |
| **记忆** | 内置情景记忆 | 无内置记忆 |
| **LLM 灵活性** | 任意提供商（Grok、DeepSeek、OpenAI、Gemini） | 仅 OpenAI |
| **最佳场景** | 结构化的研究-设计-编码-审阅链 | 探索性、并行微代理 |
| **生产就绪度** | 成熟（GitHub 45k+ stars，2026） | 实验性 |

本项目的工作流本质上是顺序的、角色结构化的（研究 -> 设计 -> 审阅 -> 编码 -> 审阅）。CrewAI 的基于角色的 Agent 模型和内置反思循环是天然的契合。Swarm 的去中心化 handoff 模型更适合开放式探索或并行数据库查询 -- 这是 Researcher Agent 未来可能的扩展方向。

#### 待办事项

- [ ] 使用真实 UMI 16S FASTQ 数据端到端测试
- [ ] 将生成的流水线与手动 DADA2+UMI-tools 工作流进行基准测试
- [ ] 添加 RAG 层（FAISS），跨运行持久化文献上下文
- [ ] 迁移至 LangGraph，实现跨会话的有状态检查点
- [ ] 并行 Researcher 子代理（Swarm 风格），用于多数据库搜索

---

### 参考文献

1. [CrewAI](https://github.com/crewai/crewai) -- 多代理编排框架
2. [UMI-tools](https://github.com/CGATOxford/UMI-tools) -- UMI 提取和去重
3. [DADA2](https://benjjneb.github.io/dada2/) -- 高分辨率扩增子去噪
4. [QIIME2](https://qiime2.org/) -- 微生物组生物信息学平台
5. [Tavily](https://tavily.com/) -- AI 综合的网络搜索 API
6. [PubMed E-utilities](https://www.ncbi.nlm.nih.gov/books/NBK25500/) -- NCBI 文献 API
7. [Grok](https://x.ai/) -- xAI 大语言模型
8. [ZymoBIOMICS](https://www.zymoresearch.com/collections/zymobiomics-microbial-community-standards) -- 微生物群落标准品
9. [mclUMI](https://doi.org/10.1093/bioinformatics/btaf068) -- 基于 Markov 聚类的 UMI 去重（2025）
10. [SPAdes](https://github.com/ablab/spades) -- De novo 基因组组装器
