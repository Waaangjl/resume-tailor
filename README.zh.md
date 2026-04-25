# resume-tailor 简历定制工具

**AI 驱动的 LaTeX 简历定制 + 求职信生成工具。**

粘贴一份 JD → 2 分钟内得到针对性修改的 `.tex` 简历 + 听起来像人写的求职信。完全本地运行，无需服务器。默认使用 [Claude Code](https://claude.ai/code)（`claude -p`），也支持 OpenAI / Ollama / 任何 LiteLLM 兼容模型。

**做什么：**
1. 从 JD 中提取关键词和要求（支持 URL、本地文件或直接粘贴文本）
2. 改写简历的 bullet points 匹配 JD 关键词——不捏造技能、不修改职位名称、不虚构数据
3. 用你自己的语气生成求职信，使用你提前写好的故事库，一次填写、反复复用

**不做什么：** 不会凭空添加技能，不改日期和职位名，不写读起来像 AI 生成的求职信。

---

## 安装要求

- **Python 3.11+**
- **[Claude Code CLI](https://claude.ai/code)** — `claude` 命令需要在 PATH 中  
  *(或者在 `config.yaml` 中设置其他模型，如 `openai/gpt-4o`、`ollama/llama3.1`)*
- **LaTeX**（可选，用于生成 PDF）— 推荐安装 [BasicTeX](https://www.tug.org/mactex/morepackages.html)（140MB），或完整版 [TeX Live](https://tug.org/texlive/)

---

## 快速开始

```bash
git clone https://github.com/Waaangjl/resume-tailor
cd resume-tailor
pip install -r requirements.txt

# 初始化你的个人档案和故事库
cp profile.example.yaml profile.yaml
cp story_bank.example.yaml story_bank.yaml

# 运行（JD 支持 URL 或本地文件）
python tailor.py --resume resumes/your_resume.tex --jd https://jobs.lever.co/company/role
python tailor.py --resume resumes/your_resume.tex --jd jds/google_swe.txt
```

输出保存在 `output/<公司>_<职位>_<日期>/`：

```
output/Google_Software_Engineer_20260101/
  resume.tex       ← 定制后的 LaTeX 简历
  resume.pdf       ← 编译好的 PDF（需要 LaTeX）
  resume.diff      ← 与原始简历的差异对比
  cover_letter.md  ← Markdown 格式的求职信
```

---

## 详细配置

### 第一步：准备你的简历

把 `.tex` 格式的简历放到 `resumes/` 目录下。如果还没有 LaTeX 简历，可以参考 `resumes/sample_resume.tex`（Jake 风格模板）。

### 第二步：填写个人档案

```bash
cp profile.example.yaml profile.yaml
```

用编辑器打开 `profile.yaml`，填入你的背景、求职动机和核心优势。这份档案会注入到每封求职信里——写得越具体，生成效果越好。

```yaml
name: 你的姓名

background: |
  简短介绍你的背景，1-3句话，说明什么让你的背景与众不同。

motivation: |
  你为什么想做这类工作？说真实原因，不要写官方套话。

edge: |
  你能做到而大多数候选人做不到的事是什么？要具体。

proud_of: |
  你最得意的一件事（具体、有数据、不装）。
```

### 第三步：填写故事库

```bash
cp story_bank.example.yaml story_bank.yaml
```

写 3–8 个你职业生涯中的真实时刻，每个故事 2–4 句话。工具会根据每份 JD 自动选最合适的故事作为求职信开头。**只需填写一次，之后每次申请都可以复用。**

```yaml
stories:
  - id: 故事的唯一ID
    tags: [consulting, finance, data]  # 用于匹配 JD 类型
    text: |
      用第一人称写一个具体的时刻。发生了什么，你做了什么，
      你意识到了什么。不要用"我很擅长XXX"这种表述——直接描述场景。
```

### 第四步（可选）：添加写作样本

把你自己写的文章、邮件等 `.txt` 文件放入 `writing_samples/`。首次运行时，工具会提取你的个人写作风格并缓存到 `writing_samples/style_guide.md`，之后每封求职信都会模仿这个风格。如果目录为空，使用内置默认风格。

### 第五步（可选）：切换 LLM

编辑 `config.yaml`：

```yaml
model: sonnet               # 默认，使用 claude -p（不需要 API key）
model: openai/gpt-4o        # 需要 OPENAI_API_KEY 环境变量
model: ollama/llama3.1      # 完全本地，需要 Ollama 在运行
model: anthropic/claude-sonnet-4-5  # 直接调用 Anthropic API（需要 ANTHROPIC_API_KEY）
```

---

## 命令参数

```bash
# 从 URL 获取 JD
python tailor.py --resume resumes/your_resume.tex --jd https://jobs.lever.co/company/role

# 从本地文件读取 JD
python tailor.py --resume resumes/your_resume.tex --jd jds/company_role.txt

# 只改简历，不生成求职信
python tailor.py --resume resumes/your_resume.tex --jd jds/role.txt --no-cover-letter

# 不编译 PDF
python tailor.py --resume resumes/your_resume.tex --jd jds/role.txt --no-pdf

# 指定模型
python tailor.py --resume resumes/your_resume.tex --jd jds/role.txt --model opus
```

---

## 工作原理

### 简历定制

LLM 在不改变事实的前提下，将 bullet point 中的描述改写为含有 JD 关键词的版本。硬性约束：不添加新技能、不修改职位名称和日期、不虚构数据。每次运行会生成 `.diff` 文件，让你在投递前清楚看到改了哪些内容。

改写优先级（从高到低）：
1. 最近一段工作/实习的 bullet points（ATS 权重最高）
2. 技能 & 专长部分（关键词密度）
3. 较早的工作经历（仅在有直接关键词匹配时修改）
4. 科研经历（保留学术语言，仅轻度增加关键词）
5. 教育背景 / 活动经历（不修改）

### 求职信生成

分三步完成（步骤 1 和 2 并行执行）：
1. **故事挑选** — 从故事库中选出最适合这份 JD 的开篇故事
2. **简历摘要** — 把 `.tex` 简历压缩为纯文本要点
3. **写信** — 生成 3 段、280–320 字的求职信，使用你的语气

求职信 Prompt 明确禁止以下空话：passionate about（热爱）、leverage（赋能）、synergies（协同效应）、results-driven（结果导向）、thought leader（思想领袖）等，并强制要求长短句交替变化，避免 AI 腔。

---

## 目录结构

```
resume-tailor/
├── tailor.py               # 主入口
├── build.py                # PDF 编译、目录管理、diff 生成
├── fetch.py                # URL 或本地文件获取 JD
├── llm.py                  # LLM 后端（claude -p 或 LiteLLM）
├── prompts.py              # 所有 LLM Prompt
├── config.yaml             # 模型 + 输出目录配置
├── profile.example.yaml    # → 复制为 profile.yaml 并填写
├── story_bank.example.yaml # → 复制为 story_bank.yaml 并填写
├── resumes/
│   └── sample_resume.tex   # Jake 风格 LaTeX 模板
├── writing_samples/        # （可选）你写的 .txt 文件
├── jds/                    # （已忽略）保存的 JD 文本
└── output/                 # （已忽略）生成的简历输出
```

---

## 运行测试

```bash
pip install pytest
pytest tests/
```

38 个测试，覆盖 HTML 解析、URL 抓取、LaTeX 清洗、diff 生成和 LLM 路由。

---

## License

MIT
