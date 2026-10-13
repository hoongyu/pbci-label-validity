# 被动 BCI 的工作负荷解码器,究竟解码了什么?

[English](README.md) | 简体中文

一项基于公开 COG-BCI 数据集的门槛驱动复现与构念效度研究。核心问题是:名义上的
**任务难度**能否作为被动 BCI 工作负荷解码器的有效训练标签,还是说用它训练出来的
解码器学到的是别的、仅仅与标签相关的东西。

> **状态:已停止,仓库作为记录归档。** 工作止于门槛 G1.2。按项目自身的规则,
> 这是一个硬停止,要求改变计划而不是绕开它。下文所列分析均已跑完并记录判决,
> G1.2 之后的任何环节都没有启动。参见[门槛状态](#门槛状态)。

## 为什么问这个问题

已发表的工作负荷解码器是用实验者给定的难度标签训练的。如果 EEG 实际上并不跟随
这个标签,那么用它训练的解码器仍然可以靠学习任务特有的特征、眼动或肌电活动、
以及任何在条件之间有差异的东西,把准确率做到高于随机水平。因此本项目测量
*名义*难度与*体验到的*工作负荷之间的落差,并追问这个落差对解码意味着什么。

四条假设支撑整个设计:

| 编号 | 主张 |
|---|---|
| H1a | 名义难度与体验到的努力程度存在分歧 |
| H1b | 这种分歧是个人层面的属性,不是噪声 |
| H2 / H2b | 分歧可预测解码失败,且分歧越大重标注的收益越大 |
| H3 | 即使范式不迁移,构念本身仍然迁移 |

H1b 是承重的:如果“被试 × 难度”的方差分量与零无法区分,H2 与 H2b 就失去基础。

## 数据

**COG-BCI**,29 名被试、每人 3 个 session、4 项认知任务,BIDS 格式下超过 100 小时
的 EEG 与 ECG 记录。

- 数据集:Zenodo [`10.5281/zenodo.6874128`](https://doi.org/10.5281/zenodo.6874128)(concept DOI,始终解析到最新版本),CC-BY 4.0
- 论文:Hinss、Jahanpour、Somon、Pluchon、Dehais 与 Roy(2023),*Scientific Data* 10:85,[`10.1038/s41597-022-01898-y`](https://doi.org/10.1038/s41597-022-01898-y)
- 本项目范围内只有 **N-Back** 与 **MATB** 这两项有分级负荷操纵的任务。PVT 与
  Flanker 不在范围内。

本仓库不转发任何数据。`data/raw` 已写入 `.gitignore`,由 `make download` 从
Zenodo 获取。

一条对复现有影响的版本说明:Zenodo 记录目前是 version 4,其更新说明写的是
“corrected an electrode name mismatch”。我们下载了 version 1
(`10.5281/zenodo.6874129`)并就 `sub-01` 与 version 4 做了比对:12 个记录的
**通道名完全一致**,每个 `.fdt` 数据文件**逐字节相同**。对这名被试而言,两个
版本没有差异。

## 门槛状态

每个门槛在 `outputs/logs/` 下都有一份日志,记录其判据、数字与判决,失败的尝试
也在其中。

| 门槛 | 检查什么 | 结果 |
|---|---|---|
| G0.1 | 环境可由锁文件复现 | 通过 |
| G0.2 | 数据已获取并盘点 | 通过 |
| G0.3 | 预处理端到端跑通 | 通过 |
| **G0.4** | **基线复现**(硬停止) | **通过** |
| G1.1 | 单元格级数据表完整 | 通过 |
| **G1.2** | **操纵检查与反常确认**(硬停止) | **Part A 通过,Part B 失败** |
| G1.3 | 分歧指标 | 通过 |
| G1.4 | 方差分解(H1b) | 通过 |
| G-LOCK | 预注册冻结 | **未到达** |
| P2 至 P4 | 重标注、迁移、论文 | 未启动 |

### G0.4,已发表的解码基线复现成功

被试内 5 折交叉验证、3 分类、在 10 通道协方差矩阵上的 Riemannian MDM,覆盖
87/87 个“被试 × session”(348 个单元格)。

| 任务 | 实测 | 已发表 | 接受区间 |
|---|---|---|---|
| MATB | **71.88%** | 69.40% | 66.40 至 72.40(±3.0 pp) |
| N-Back | **64.30%** | 64.97% | 61.97 至 67.97(±3.0 pp) |

三条方向性判据同样成立,包括 session 2 处那个非单调的峰值,每个 session 的复现
误差都在 1.4 pp 以内。

### G1.1,单元格数据表

522/522 行(29 名被试 × 2 项任务 × 3 个 session × 3 个难度),32 列。RSME 在
**8/522 个单元格(1.53%)**中缺失,阈值为低于 10%。

### G1.2,Part A 复现成功,Part B 没有

**Part A** 复现了已发表的操纵检查:三个 F 统计量与发表值吻合到四位有效数字。
这把条件分配、N-Back 的降序编号以及 session 映射全部钉死了。

**Part B** 需要确认本项目赖以立论的那个反常现象:在 N-Back 中,主观、行为与心脏
测量都跟随难度,而 theta 与 alpha 功率不跟随。它只成立了一半。

在 3 种 ROI 定义与 4 种分段剔除判据构成的 12 种组合下测量,29 名被试:

| 判据 | 成立于 |
|---|---|
| MATB:额区 theta 有难度效应 | 12/12 |
| MATB:后部 theta 有难度效应 | 12/12 |
| MATB:后部 alpha 有难度效应 | 12/12 |
| MATB:后部 alpha 随难度*上升* | 12/12 |
| N-Back:alpha 无 session 效应 | 12/12 |
| N-Back:theta 无难度效应 | 7/12,参数依赖 |
| **N-Back:alpha 无难度效应** | **0/12** |

已发表的 N-Back **theta** 零效应复现成功。N-Back **alpha** 的零效应在所有尝试过
的组合下都不成立,包括论文自己的电极簇与它自己的 2 SD 剔除判据。alpha 在三个
ROI 上都随负荷单调下降,而且 **26/29、27/29 与 25/29 名被试各自**都表现出 2-back
的 alpha 低于 0-back。

以下候选解释均已用测量而非论证排除:预处理变体、分段长度、四种剔除判据、三种
ROI 定义、频带与功率定义、时间进程与呈现顺序、ICA 不收敛、坏道插值、样本量、
条件到文件的映射,以及数据集版本。管线不灵敏这一解释也被排除,因为同一份数据上
MATB 达到了 F = 166。

alpha 还在**两项任务中朝相反方向移动**,在 N-Back 中随负荷下降,在 MATB 中随
负荷上升。而这两项都被描述为工作负荷操纵。

### G1.3,分歧指标

58/58 行(29 名被试 × 2 项任务)。D_subj 与 D_beh 定义为名义难度与 RSME 或行为
表现之间的 `1 − τ_b`,在每名被试每项任务的 9 个单元格上计算,并给出逐被试的
自举置信区间。

清单之外有三个结果:

- **D = 0 在实践中达不到。** τ_b 惩罚的是并列结构的不匹配,而不只是排序的不匹配,
  而名义难度永远是三组各三个并列。一名被试若跨难度层级排序完美但层级内有波动,
  得分是 D = 0.134。
- **逐被试的区间很宽**,N-Back 的 D_subj 中位宽度为 0.773,而量程是 [0, 2]。
  只有 2/29 名 N-Back 被试与 0/29 名 MATB 被试的区间能越过该指标自身的下限。
- **D_subj 与 D_beh 并不一致**(N-Back ρ = −0.153,MATB ρ = +0.311,均不显著)。
  分析规范把这种情况视为一项发现,而不是缺陷。

### G1.4,方差分解,H1b 成立

按任务分别拟合 `RSME ~ 1 + difficulty + (1 + difficulty | subject) + (1 | session)`,
采用交叉随机效应与 2000 次被试层面的自举抽样。

| 任务 | “被试 × 难度”斜率方差 | 95% CI | H1b |
|---|---|---|---|
| N-Back | 35.07 | [6.67, 62.07] | 成立 |
| MATB | 48.51 | [18.06, 75.09] | 成立 |

两项任务中都是 0/2000 次抽样未能收敛。被试 ICC 为 0.435(N-Back)与
0.480(MATB)。

`variance.py --simulate` 能从合成数据中还原已知的方差分量,在信任这个拟合器
之前值得先跑一次。它抓出过一个错误:所有方差分量被放大约 40 倍,而残差保持正确,
仅看输出完全察觉不到。

## 两套预处理变体

已发表工作使用了两条管线,把它们混用是基线复现失败最可能的原因。两条都已实现:

| | ML 变体(`src/preprocess/run.py`) | 描述性变体(`src/preprocess/descriptive.py`) |
|---|---|---|
| 顺序 | 先分段,再逐段清理 | 先清理连续信号,再分段 |
| 分段长度 | 5 秒 | 0.5 秒 |
| 分段剔除 | 关闭 | 开启 |
| alpha 频带 | 8 至 12 Hz | 8 至 13 Hz |
| 用于 | G0.4 解码基线 | G1.2 频带功率分析 |

描述性变体的频带功率是先对**连续**信号滤波、再分段计算的。在 0.5 秒下一个分段
只有 126 个采样点,而 theta 的 FIR 带通滤波器需要 413 点的核,因此逐段滤波会使
结果失真。

## 预注册

`prereg/protocol.md` 是**一个占位文件,不是协议**。它应在 P1 期间撰写、在 G-LOCK
冻结,而本项目从未到达 G-LOCK。这里没有任何内容是预注册过的。

真正存在的是 `deviations.md`:每一处对计划的偏离,都记录了它相对于“看到结果”
这一时点的先后。其中包含事先承诺的决策规则,也包含一次因为规则偏向于确认假设
而被替换掉的记录。

## 如何复现

Python 3.12。依赖固定在 `env/requirements.lock`(72 个包,含 MNE-Python、
mne-icalabel、pyriemann 与 statsmodels)。

```bash
python -m venv .venv
.venv/Scripts/pip install -r env/requirements.lock   # Windows
# .venv/bin/pip install -r env/requirements.lock     # POSIX

make download-check    # 预检:磁盘空间与记录元数据,不下载任何东西
make download          # 从 Zenodo 下载约 29.5 GB,可续传
make verify-raw        # 对每个本地文件做 md5 校验,比对 Zenodo API
make extract           # 原地解压 sub-*.zip

make inventory         # G0.2
make baseline          # G0.4   解码基线
make cells             # G1.1   单元格级数据表
make manipulation      # G1.2 Part A
make anomaly           # G1.2 Part B,会先跑描述性变体的扫描
make confound          # G1.2 的呈现顺序对照
make divergence        # G1.3
make variance          # G1.4
make test              # pytest
```

`make all` 跑完整条分析链,不重新下载。预处理整个数据集每个变体需要数小时。
`sweep.ps1` 与 `supervise.ps1` 的存在是因为原机器上曾有一个 worker 在内存压力下
被杀死,扫描随即空转,而从外面看它仍像在工作。

所有随机种子固定在 `config.yaml`,该文件同时记录通道集合、频带边界与清理阈值。
其中每一个偏离参考文档的取值,都在 `deviations.md` 里有对应条目。

## 仓库结构

```
src/io/            数据集下载、校验、盘点,以及任务编码的断言保护
src/preprocess/    两套预处理变体与一个内存守卫
analyses/P0_*/     G0.4 解码基线
analyses/P1_*/     单元格表、操纵检查、分歧指标、方差分解、顺序混淆对照
outputs/logs/      每次门槛尝试一份日志,含失败的尝试
outputs/tables/    每个判决背后的数字
deviations.md      每一处对计划的偏离,带时序
prereg/            占位协议,从未冻结
```

`.claude/skills/pbci-label-validity/` 存放项目自身的操作规则、PRD、门槛定义,
以及关于数据集与分析规范的参考笔记。

## 引用数据集

```bibtex
@article{hinss2023cogbci,
  title   = {Open multi-session and multi-task EEG cognitive Dataset for
             passive brain-computer Interface Applications},
  author  = {Hinss, Marcel F. and Jahanpour, Emilie S. and Somon, Bertille and
             Pluchon, Lou and Dehais, Frederic and Roy, Raphaelle N.},
  journal = {Scientific Data},
  volume  = {10},
  pages   = {85},
  year    = {2023},
  doi     = {10.1038/s41597-022-01898-y}
}
```

## 许可证

**未定。** 本仓库没有许可证文件,因此默认版权适用,未授予任何权限。COG-BCI
数据集由其作者以 CC-BY 4.0 单独授权,本仓库不转发该数据。
