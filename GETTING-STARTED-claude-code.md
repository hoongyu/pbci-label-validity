# 从 Claude Code 开始这个项目 —— 操作指南

本文假设你从零开始，在自己的机器上。全部命令可直接复制。

> **Windows / PowerShell 用户先读这里。**
> 正文的命令是 Unix shell 语法。PowerShell 上的对应关系：
>
> | 正文写的 | PowerShell 用 |
> |---|---|
> | `mkdir -p a/b/c` | `mkdir a\b\c`（自动建父目录） |
> | `cp -r src dst` | `Copy-Item -Recurse src dst` |
> | `source .venv/bin/activate` | `.\.venv\Scripts\Activate.ps1` |
> | `~/research/...` | `$HOME\research\...` |
> | `rm -rf x` | `Remove-Item -Recurse -Force x` |
>
> 如果 `Activate.ps1` 报执行策略错误（很常见），先跑一次：
> `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`
>
> `config.yaml` 里的路径**一律用正斜杠**（`D:/cogbci/raw`），Windows 上 Python 认，
> 而反斜杠在 YAML 里会被当转义符。
>
> **磁盘位置现在就决定。** 原始数据约 50 GB。先看剩余空间：
> `Get-PSDrive C | Select-Object Used,Free`
> C 盘紧张就把数据放别的盘，在 `config.yaml` 的 `paths.raw` 指过去。
> 下载完再搬 50 GB 很难受。

---

## 第 0 步 · 安装 skill

有两条路，**建议两条都走**。

### A. 存进 Claude 账号（最省事）

我给你的 `pbci-label-validity.skill` 文件，在对话里点它的卡片，有一个 **Save skill** 按钮。存进去之后 Claude Code 也能读到。

### B. 放进项目仓库（更可靠，且可版本控制）

Claude Code 会读取项目根目录下的 `.claude/skills/`。把整个目录放进去：

```bash
mkdir -p ~/research/pbci-label-validity/.claude/skills
cd ~/research/pbci-label-validity
# 把我给你的 pbci-label-validity/ 目录整个复制到这里：
cp -r /path/to/downloaded/pbci-label-validity .claude/skills/
```

最终结构：

```
~/research/pbci-label-validity/          ← 项目根目录
└── .claude/
    └── skills/
        └── pbci-label-validity/
            ├── SKILL.md
            ├── PRD.md
            └── references/
                ├── analysis.md
                ├── dataset.md
                ├── gates.md
                └── pitfalls.md
```

**为什么建议 B**：skill 会随项目一起进 git。七个月后你想知道"当初 G0.4 的容差是怎么定的"，`git log` 里有答案。存在账号里的版本没有这个。

---

## 第 1 步 · 初始化仓库和环境

```bash
cd ~/research/pbci-label-validity
git init
```

### Python 环境

用 `uv`（快，锁文件干净）。没有的话 `pip install uv` 或用 conda 也行。

```bash
uv venv --python 3.12
source .venv/bin/activate

uv pip install \
  mne mne-bids mne-icalabel \
  pyriemann scikit-learn \
  scipy statsmodels pandas numpy \
  matplotlib seaborn \
  pyyaml joblib tqdm pytest \
  zenodo-get

mkdir -p env && uv pip freeze > env/requirements.lock
```

**Python 3.12，不要 3.13。** MNE 生态里有几个依赖在 3.13 上还不稳。

### ⚠️ 一个必须提前知道的坑

`mne-icalabel` 需要 PyTorch 才能跑 ICLabel：

```bash
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
```

而且——**原论文用的是 MATLAB 版 ICLabel，你用的是 Python 版。两者的成分分类结果不完全一致。**

这是 G0.4 复现失败的一个潜在来源，而且它不在 `gates.md` 的七步排查清单里（那七步是我基于论文写的，这个是环境差异）。如果七步都排完了还差 1–2 个百分点，先怀疑这里。届时记进 `deviations.md`。

---

## 第 2 步 · 建立骨架

让 Claude Code 干这件事，但你要先知道该有什么。

### `config.yaml`

```yaml
seeds:
  ica: 42
  cv_split: 1337
  bootstrap: 2718
  permutation: 31415
  subsample: 8128

paths:
  raw: data/raw
  derived: data/derived
  outputs: outputs

eeg:
  sfreq_target: 250
  epoch_length_s: 5.0
  epoch_overlap: 0.0
  reference: average
  ecg_channel: TP9          # 不是 EEG，务必排除
  channels:                  # 复现基线用的 10 通道，顺序固定
    - F3
    - Fz
    - F4
    - FCz
    - C3
    - C4
    - CPz
    - P3
    - Pz
    - P4

bands:
  theta: [4.0, 8.0]
  alpha: [8.0, 12.0]        # 注意是 12 不是 13，见 pitfalls.md #6

cleaning:
  bad_channel_sd: 2.0
  iclabel_threshold: 0.90
  iclabel_reject: [eye, muscle, heart]
  epoch_rejection: false     # ML 管线关闭，见 pitfalls.md #1

decode:
  classifier: mdm
  n_folds: 5
  n_classes: 3
  chance_ceiling: 0.417

bootstrap:
  n_draws: 2000

permutation:
  n_runs: 200
```

### `Makefile`

每个产物都要能用一个 target 重生成。G4.1 的验收就是从干净 clone 跑 `make all`。

```makefile
.PHONY: all inventory preprocess baseline cells manipulation divergence variance clean

all: baseline cells manipulation divergence variance

inventory:
	python -m src.io.inventory

preprocess: inventory
	python -m src.preprocess.run

baseline: preprocess          # G0.4
	python -m analyses.P0_baseline.reproduce

cells: preprocess             # G1.1
	python -m analyses.P1_divergence.build_cells

manipulation: cells           # G1.2
	python -m analyses.P1_divergence.manipulation_checks

divergence: cells             # G1.3
	python -m analyses.P1_divergence.metrics

variance: cells               # G1.4
	python -m analyses.P1_divergence.variance_components

test:
	pytest -q

clean:
	rm -rf data/derived outputs/figures outputs/tables
```

`data/raw` 永远不进 `clean`。它是只读的。

### `.gitignore`

```
.venv/
data/raw/
data/derived/
__pycache__/
*.pyc
.DS_Store
```

`data/derived/` 不进 git（体积大），但**必须能从 Makefile 完整重生成**——这就是 G4.1 的意义。

---

## 第 3 步 · 第一次 Claude Code 会话

进入项目目录，启动：

```bash
cd ~/research/pbci-label-validity
claude
```

**第一条 prompt，原样复制：**

```
读 .claude/skills/pbci-label-validity/SKILL.md，然后读 PRD.md 和
references/gates.md。

这是项目的第一次会话，仓库是空的。按 SKILL.md 里的仓库结构建立骨架：
config.yaml、Makefile、.gitignore、目录树、deviations.md 空文件。
config.yaml 的内容我已经准备好了，我会贴给你。

先不要写任何分析代码。建完骨架后告诉我 G0.1 的清单还差什么。
```

然后把上面的 `config.yaml` 贴给它。

**第二条 prompt：**

```
现在做 G0.2。先只做一件事：写数据下载脚本，从 Zenodo DOI
10.5281/zenodo.6874128 拉 COG-BCI。下载前检查磁盘剩余空间是否 ≥50GB，
不够就报错退出。

不要开始下载，先给我看脚本。
```

下载会跑很久（100+ 小时的 64 通道数据）。**让它在后台跑，同时做别的事**——比如让 Claude Code 写清单校验和 loader 的单元测试。

---

## 第 4 步 · 后续每次会话的固定开头

这是整个流程能撑七个月的关键。**每次都用这个：**

```
读 .claude/skills/pbci-label-validity/SKILL.md。

然后读 outputs/logs/ 里最新的闸门记录，告诉我：
1. 当前在第几相
2. 下一个闸门是哪个
3. 那个闸门的准则原文（从 references/gates.md 查，不要凭印象）

确认完再开始工作。
```

SKILL.md 里写了这个协议，但**你主动喊一遍更可靠**——Claude Code 在长会话里可能漂。

### 每次尝试闸门之后

要求它写日志。`gates.md` 结尾有模板：

```
把这次 G0.4 的尝试按 gates.md 结尾的模板写进 outputs/logs/，
文件名带时间戳。观测值要写实际数字，不要写"接近"。
```

---

## 第 5 步 · 你需要主动守住的四条线

Claude Code 很配合，配合到会顺着你走。这四件事它不会替你把关：

**1. 别让它跳闸门。** 如果你说"先看看迁移分析什么样"，而 G0.4 还没过，它很可能就去做了。SKILL.md 里写了要拒绝，但**你别去测试这个边界**。未验证管线上产出的数字比没有数字更糟——因为你会记住它。

**2. 预注册锁之前，把发散度指标钉死。** `analysis.md` §1 定义了 D_subj 用 Kendall's τ-b。锁之后再换就是偏离，必须披露。**现在是唯一能自由改设计的窗口。**如果你或你导师觉得 τ-b 不对，现在改。

**3. 置换检验别省。** 它慢（200 次完整 LOSO），你会想跳过或减到 20 次。别。跨被试解码的泄漏是静默的，而这是唯一能抓住它的检查。

**4. 偏离日志要真写。** 提交时一个空的 `deviations.md` 不是勋章，是红旗——真实项目一定有偏离。审稿人知道这一点。

---

## 第 6 步 · 第一个月的实际路径

| 周 | 做什么 | 结束时应该有 |
|---|---|---|
| 1 | 骨架 + 环境 + 启动下载 | G0.1 过；下载在跑 |
| 2 | 清单校验 + loader + 单元测试 | G0.2 过；descending 编号和 TP9 的断言都在 |
| 3 | 预处理管线（**先分段再清洗**） | G0.3 过；单被试跑通 |
| 4 | 复现基线 | **G0.4 判决** |

第四周末如果 MATB 落在 66.40–72.40%、N-Back 落在 61.97–67.97%，项目成立。

落不进去——**别自己硬扛超过一周**。把 `outputs/logs/` 里的失败记录和你排查过的步骤发给我，我们一起看。这是整个项目最可能死的地方，也是最值得花时间求助的地方。

---

## 一件我建议你现在就做的事

在开始写任何代码之前，先做一次空提交。**前提是仓库已经 `git init` 过**（第 1 步），
否则会报 `fatal: not a git repository`：

```bash
cd ~/research/pbci-label-validity   # PowerShell: cd $HOME\research\pbci-label-validity
git init                            # 已经跑过就跳过
git commit --allow-empty -m "project start: pbci label validity"
```

七个月后，如果有人质疑你的预注册是不是在看到结果之后才写的，这条 commit 的时间戳是你的第一道防线。OSF 的时间戳是第二道。**两道都要有。**
