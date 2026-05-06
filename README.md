# exp_viewer

实验数据可视化工具包。用 JSON 文件记录超参数和实验结果，通过命令行一键生成图表、导出报告或启动交互式仪表盘。支持多目录加载、跨项目横向对比、14 种图表类型和列可见性控制。

## 目录

- [快速开始](#快速开始)
- [数据目录结构](#数据目录结构)
- [字段类型系统](#字段类型系统)
- [类型配置文件 (fields.json)](#类型配置文件-fieldsjson)
- [CLI 命令参考](#cli-命令参考)
- [多目录与项目对比](#多目录与项目对比)
- [交互式服务端](#交互式服务端)
- [REST API 参考](#rest-api-参考)
- [Python API 参考](#python-api-参考)
- [静态 HTML 导出](#静态-html-导出)
- [SQLite 持久化](#sqlite-持久化)
- [完整示例](#完整示例)

---

## 快速开始

### 安装

```bash
pip install -e .
```

需要 Python >= 3.11。

### 30 秒上手

1. 创建实验目录：

```bash
mkdir -p my_experiments/run_001
```

2. 写入超参数和结果：

```bash
# config.json — 超参数
cat > my_experiments/run_001/config.json << 'EOF'
{
    "learning_rate": 0.001,
    "batch_size": 32,
    "optimizer": "adam"
}
EOF

# results.json — 实验结果
cat > my_experiments/run_001/results.json << 'EOF'
{
    "accuracy": 0.95,
    "loss": 0.032,
    "epochs": 12
}
EOF
```

3. 查看摘要：

```bash
exp-viewer info my_experiments/
```

4. 启动交互式仪表盘：

```bash
exp-viewer serve my_experiments/
```

浏览器访问 `http://127.0.0.1:8050`，即可看到表格和图表。

5. 导出静态 HTML 报告：

```bash
exp-viewer export my_experiments/ -o report.html
```

---

## 数据目录结构

exp_viewer 通过扫描目录来发现实验数据。基本结构如下：

```
my_experiments/                  ← 实验根目录（传给 CLI 的 path 参数）
├── fields.json                  ← [可选] 字段类型配置 & 列可见性
├── run_001/                     ← 一个实验（子目录）
│   ├── config.json              ← 超参数（必需，与 results.json 至少存在一个）
│   ├── results.json             ← 实验结果（必需，与 config.json 至少存在一个）
│   └── metadata.json            ← [可选] id、name、tags、created_at
├── run_002/
│   ├── config.json
│   └── results.json
└── run_003/
    ├── config.json
    ├── results.json
    └── metadata.json
```

### 规则

- 实验根目录下的每个**子目录**被视为一个实验
- 子目录名作为默认的实验 ID（除非有 `metadata.json` 另行指定）
- 子目录中至少包含 `config.json` 或 `results.json` 之一，否则被跳过
- 不包含 JSON 文件的子目录（如 `.git`、`__pycache__`）会被自动忽略
- `fields.json` 放在实验根目录，对所有实验生效

### config.json

记录实验的超参数配置。纯 JSON 键值对：

```json
{
    "learning_rate": 0.001,
    "batch_size": 32,
    "optimizer": "adam",
    "use_augmentation": true,
    "train_pct": 0.8
}
```

### results.json

记录实验的结果指标。纯 JSON 键值对：

```json
{
    "accuracy": 0.95,
    "loss": 0.032,
    "f1_score": 0.94,
    "converged": true,
    "epochs": 12
}
```

### metadata.json（可选）

覆盖默认的实验元信息：

```json
{
    "id": "my_experiment_v2",
    "name": "Learning Rate Sweep Run 2",
    "tags": ["sweep", "lr", "v2"],
    "created_at": "2026-04-27T10:30:00Z"
}
```

| 字段 | 类型 | 说明 | 默认值 |
|------|------|------|--------|
| `id` | string | 实验唯一标识 | 子目录名 |
| `name` | string | 显示名称 | 同 id |
| `tags` | string[] | 标签列表 | `[]` |
| `created_at` | string | ISO 8601 时间戳 | 目录修改时间 |

如果不提供 `metadata.json`，系统会使用目录名作为 id 和 name，并使用目录的文件系统修改时间作为 `created_at`。

---

## 字段类型系统

exp_viewer 支持 4 种字段类型：

| 类型 | 标识符 | JSON 值示例 | 显示效果 | 适用场景 |
|------|--------|-------------|----------|----------|
| **numeric** | `"numeric"` | `42`, `0.032` | `42`, `0.0320` | 通用数值 |
| **percentage** | `"percentage"` | `0.95`, `95.0` | `95.00%`, `95.0%` | 百分比（支持 0-1 和 0-100 两种范围） |
| **boolean** | `"boolean"` | `true`, `false` | `True`, `False` | 布尔标志 |
| **string** | `"string"` | `"adam"` | `adam` | 文本、枚举 |

### 类型覆盖关系

类型之间存在兼容性层级（从窄到宽）：

```
BOOLEAN ⊂ NUMERIC ⊂ PERCENTAGE ⊂ STRING
```

当同一字段在不同实验中有不同类型的值时，系统自动选择**最小兼容类型**：

| 实验 A 的值 | 实验 B 的值 | A 的推断类型 | B 的推断类型 | 最终公共类型 |
|-------------|-------------|-------------|-------------|-------------|
| `0.01` | `0.001` | NUMERIC | NUMERIC | **NUMERIC** |
| `true` | `false` | BOOLEAN | BOOLEAN | **BOOLEAN** |
| `true` | `1` | BOOLEAN | NUMERIC | **NUMERIC** |
| `0.95` | `0.97` | PERCENTAGE | PERCENTAGE | **PERCENTAGE** |
| `0.01` | `"auto"` | NUMERIC | STRING | **STRING** |
| `true` | `"yes"` | BOOLEAN | STRING | **STRING** |

### 类型解析优先级

系统按以下顺序确定每个字段的类型：

1. **`fields.json` 显式声明**（最高优先）— 用户手动指定的类型，始终优先
2. **跨实验最小兼容类型** — 收集所有实验中该字段的值，分别推断类型，取覆盖关系上的最小公共类型
3. **单值名称推断**（兜底）— 根据值的 JSON 类型推断，字段名含特定关键词时识别为 percentage

### 名称自动推断规则

当没有 `fields.json` 且只有单个实验时，按以下规则推断：

| JSON 值类型 | 推断结果 | 例外 |
|-------------|---------|------|
| `bool` (`true`/`false`) | `boolean` | — |
| `int` / `float` | `numeric` | 字段名含 `pct`、`percent`、`accuracy`、`score`、`ratio` → `percentage` |
| `string` | `string` | — |

示例：
- `"accuracy": 0.95` → 自动识别为 **percentage**
- `"f1_score": 0.94` → 自动识别为 **percentage**
- `"train_pct": 0.8` → 自动识别为 **percentage**
- `"loss": 0.032` → **numeric**（名称无百分比暗示）
- `"optimizer": "adam"` → **string**
- `"use_augmentation": true` → **boolean**

---

## 类型配置文件 (fields.json)

放在实验根目录下，用于显式声明字段类型和列可见性。**只需声明需要覆盖的字段，其余字段走自动推断。**

### 基本格式

```json
{
    "learning_rate": "numeric",
    "batch_size": "numeric",
    "optimizer": "string",
    "use_augmentation": "boolean",
    "train_pct": "percentage",
    "accuracy": "percentage",
    "loss": "numeric",
    "f1_score": "percentage",
    "converged": "boolean",
    "epochs": "numeric"
}
```

### 分组格式

也可以按超参数/结果分组（效果与扁平格式相同）：

```json
{
    "hyperparameters": {
        "learning_rate": "numeric",
        "optimizer": "string"
    },
    "results": {
        "accuracy": "percentage",
        "loss": "numeric"
    }
}
```

### 列可见性控制

除类型声明外，`fields.json` 还支持控制字段在表格中的默认可见性。使用对象格式：

```json
{
    "dropout_rate": {"type": "percentage", "visible": false},
    "internal_flag": {"visible": false}
}
```

- `"visible": false` — 该字段在表格列选择器中默认不勾选，但仍可手动启用
- `"visible": true`（默认）— 该字段在表格中默认显示

### 使用场景

- 字段名不含百分比关键词，但实际是百分比（如 `"dropout_rate": "percentage"`）
- 跨实验值类型不一致，需要强制指定（如 `"lr": "string"` 强制把 `0.01` 当字符串处理）
- 名称推断结果不符合预期时手动修正
- 隐藏不常用的中间字段（如 `"debug_info": {"visible": false}`）

### 增量覆盖

`fields.json` 只覆盖其中声明的字段。未声明的字段仍然走自动推断。例如只写一条：

```json
{"dropout_rate": "percentage"}
```

则 `dropout_rate` 会被识别为 percentage，`accuracy` 仍由名称自动推断为 percentage，`loss` 推断为 numeric。

---

## CLI 命令参考

安装后提供 `exp-viewer` 命令，支持 4 个子命令：

### exp-viewer info

打印实验摘要，不修改任何文件。

```bash
exp-viewer info <path>
```

| 参数 | 说明 |
|------|------|
| `path` | 实验根目录路径或 `.db` 数据库文件路径 |

示例输出：

```
Experiments: 3
Hyperparameter keys: learning_rate, batch_size, optimizer, use_augmentation, train_pct
Result keys: accuracy, loss, f1_score, converged, epochs

  [run_001] run_001
    hp.learning_rate = 0.0010
    hp.batch_size = 32
    hp.optimizer = adam
    hp.use_augmentation = True
    hp.train_pct = 80.00%
    res.accuracy = 95.00%
    res.loss = 0.0320
    res.f1_score = 94.00%
    res.converged = True
    res.epochs = 12

  [run_002] run_002
    ...
```

### exp-viewer scan

扫描实验目录，将结果存入 SQLite 数据库。适合数据持久化和后续查询。

```bash
exp-viewer scan <path> [-o output.db]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `path` | — | 实验根目录路径 |
| `-o`, `--output` | `experiments.db` | SQLite 输出文件路径 |

### exp-viewer serve

启动交互式 Web 仪表盘。支持多目录加载以实现跨项目对比。

```bash
# 单目录
exp-viewer serve <path> [--host HOST] [--port PORT]

# 多目录（跨项目对比）
exp-viewer serve <path1> <path2> ... [--labels label1,label2,...] [--host HOST] [--port PORT]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `paths` | — | 一个或多个实验根目录路径或 `.db` 数据库文件路径 |
| `--labels` | 各目录 basename | 逗号分隔的项目标签，一一对应 paths |
| `--host` | `127.0.0.1` | 绑定地址 |
| `--port` | `8050` | 绑定端口 |
| `--db` | 内存数据库 | SQLite 数据库路径 |

启动后浏览器访问 `http://<host>:<port>` 即可。按 `Ctrl+C` 停止。

### exp-viewer export

导出为自包含的静态 HTML 文件，可直接浏览器打开，无需服务端。

```bash
exp-viewer export <path> [-o output.html] [--title TITLE]
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `path` | — | 实验根目录路径或 `.db` 数据库文件路径 |
| `-o`, `--output` | `experiments.html` | 输出 HTML 文件路径 |
| `--title` | `Experiment Viewer` | 页面标题 |

导出的 HTML 文件内嵌 Plotly.js（从 CDN 加载）、表格和图表数据，通过标签页切换。

---

## 多目录与项目对比

exp_viewer 支持同时加载多个实验目录，为不同项目打上标签，实现跨项目横向对比。

### 基本用法

```bash
# 加载两个实验目录，自动使用目录名作为项目标签
exp-viewer serve project_a/ project_b/

# 自定义项目标签
exp-viewer serve project_a/ project_b/ --labels CNN,Transformer
```

### 项目标签规则

- 未指定 `--labels` 时，默认使用目录的 basename 作为项目名
- 每个实验携带 `project` 字段，贯穿整个管线（表格、图表、API、导出）
- 多项目时，表格自动显示 Project 列，图表支持按 project 着色/分组

### UI 中的项目功能

- **Project 筛选下拉框** — 只显示特定项目的实验
- **表格 Project 列** — 显示每个实验所属项目（仅多项目时出现）
- **图表按 project 着色** — 在 Color 下拉框中选择 `project`
- **自动项目对比图** — 导出 HTML 时，多项目数据自动生成按项目分组的箱线图

### 向后兼容

单目录模式完全向后兼容：

```bash
exp-viewer serve my_experiments/   # 单目录，行为不变
exp-viewer serve experiments.db    # 单数据库文件，行为不变
```

### 实验详情页

在表格中点击实验 ID 链接，跳转到详情页，显示项目徽章（如果有项目标签）。

---

## 交互式服务端

运行 `exp-viewer serve` 后，浏览器访问的仪表盘提供以下功能：

### 表格视图

- 显示所有实验的超参数和结果
- 列头分为 **Hyperparameters** 和 **Results** 两组，带不同背景色
- 多项目时自动显示 **Project** 列
- 点击 **Sort by** 下拉框选择排序字段，支持升序/降序
- **Filter** 输入框支持按字段筛选，格式为 `字段名:操作符:值`
- **Columns** 按钮打开列选择器，可控制显示哪些列（支持全选/全不选/按组切换）
- 多项目时显示 **Project** 筛选下拉框

### 列可见性控制

点击 **Columns** 按钮打开列选择面板：

- 复选框控制每列的显示/隐藏
- **All** / **None** 按钮快速全选/全不选
- **Toggle HP** / **Toggle Results** 按钮按组切换
- 列的默认选中状态可通过 `fields.json` 的 `visible` 属性配置

### 图表视图

切换到 **Chart** 标签页，选择图表类型和轴字段。支持 14 种图表：

| 图表 | 类型标识 | 用途 | 参数 |
|------|---------|------|------|
| **Bar** | `bar` | 比较不同实验的同一指标 | X, Y, Color, Mode(grouped/stacked) |
| **Line** | `line` | 多指标趋势 | X, Y(逗号分隔多个) |
| **Scatter** | `scatter` | 两个指标的相关性 | X, Y, Color, Size |
| **Parallel Coordinates** | `parallel_coordinates` | 多维超参数对比 | Dimensions, Color |
| **Heatmap** | `heatmap` | 参数-指标矩阵 | X, Y, Color(值) |
| **Box** | `box` | 指标分布与离群值 | Group, Y, Color |
| **Violin** | `violin` | 指标分布密度 | Group, Y, Color |
| **3D Scatter** | `scatter_3d` | 三维指标关系 | X, Y, Z, Color, Size |
| **Pie** | `pie` | 指标占比 | Labels, Values |
| **Histogram** | `histogram` | 指标值分布 | X, Color, Mode, Bins |
| **Contour** | `contour` | 二维等高线 | X, Y, Color(值) |
| **Radar** | `radar` | 多维雷达图 | Dimensions, Labels |
| **Area** | `area` | 多指标面积图 | X, Y(逗号分隔多个) |
| **Funnel** | `funnel` | 漏斗图 | Labels, Values |

多项目时，所有图表的 Color 下拉框均包含 `project` 选项，可按项目着色。

### 筛选语法

在 Filter 输入框中使用 `字段名:操作符:值` 格式：

| 操作符 | 含义 | 示例 |
|--------|------|------|
| `eq` | 等于 | `optimizer:eq:adam` |
| `ne` | 不等于 | `optimizer:ne:sgd` |
| `gt` | 大于 | `accuracy:gt:0.9` |
| `lt` | 小于 | `loss:lt:0.05` |
| `gte` | 大于等于 | `accuracy:gte:0.95` |
| `lte` | 小于等于 | `epochs:lte:20` |
| `contains` | 包含子串 | `id:contains:run` |

示例：筛选 accuracy > 90% 的实验，在 Filter 输入框输入：

```
accuracy:gt:0.9
```

然后点击 **Apply** 按钮。

### 导出

点击页面头部的 **Export HTML** 链接，下载当前数据的静态 HTML 报告。

---

## REST API 参考

服务端同时提供 REST API，可用于脚本集成。

### GET /api/experiments

返回所有实验的 JSON 列表。

```json
[
    {
        "id": "run_001",
        "name": "run_001",
        "project": "my_experiments",
        "created_at": "2026-04-27T10:00:00+00:00",
        "tags": [],
        "hyperparameters": {
            "learning_rate": {"value": 0.001, "type": "numeric"},
            "optimizer": {"value": "adam", "type": "string"}
        },
        "results": {
            "accuracy": {"value": 0.95, "type": "percentage"},
            "loss": {"value": 0.032, "type": "numeric"}
        }
    }
]
```

### GET /api/experiments/{id}

返回单个实验的详情。404 返回 `{"error": "Not found"}`。

### GET /api/fields

返回所有字段名及其类型信息。

```json
{
    "hyperparameters": ["learning_rate", "batch_size", "optimizer"],
    "results": ["accuracy", "loss", "f1_score"],
    "fields": {
        "learning_rate": {"type": "numeric", "category": "hyperparameter", "visible": true},
        "accuracy": {"type": "percentage", "category": "result", "visible": true}
    },
    "projects": ["project_a", "project_b"]
}
```

### GET /api/table

返回 HTML 表格片段。支持查询参数：

| 参数 | 示例 | 说明 |
|------|------|------|
| `sort_by` | `accuracy` | 排序字段 |
| `sort_desc` | `true` | 是否降序 |
| `columns` | `learning_rate,accuracy,loss` | 只显示指定列 |
| `project` | `project_a` | 按项目筛选 |
| `filter_{field}` | `filter_accuracy=gt:0.9` | 按字段筛选 |

### GET /api/chart/{type}

返回 Plotly JSON 图表数据。`type` 可选：`bar`、`line`、`scatter`、`parallel_coordinates`、`heatmap`、`box`、`violin`、`scatter_3d`、`pie`、`histogram`、`contour`、`radar`、`area`、`funnel`。

| 参数 | 适用图表 | 说明 |
|------|---------|------|
| `x` | bar, line, scatter, heatmap, scatter_3d, box, violin, pie, histogram, contour, area, funnel | X 轴 / Labels 字段 |
| `y` | bar, line, scatter, heatmap, scatter_3d, box, violin, pie, area | Y 轴 / Values 字段（line/area 支持逗号分隔多个） |
| `z` | scatter_3d | Z 轴字段 |
| `color` | scatter, scatter_3d, parallel_coordinates, box, violin, histogram | 颜色维度字段 |
| `size` | scatter, scatter_3d | 气泡大小字段；heatmap/contour 中为值字段 |
| `dimensions` | parallel_coordinates, radar | 逗号分隔的维度字段列表 |
| `group_mode` | bar, histogram | `grouped`（默认）/ `stacked` / `overlay` |
| `nbins` | histogram | 直方图分箱数（默认 20） |
| `title` | 全部 | 图表标题 |

### POST /api/scan

重新扫描实验目录，刷新数据库。返回 `{"loaded": N}`。

### GET /export

下载当前数据的静态 HTML 报告。

---

## Python API 参考

exp_viewer 也可以作为 Python 库使用：

```python
from exp_viewer import (
    scan_directory,
    export_html,
    Database,
    ExperimentSet,
    Experiment,
    FieldValue,
    FieldType,
)
from pathlib import Path
```

### 扫描实验目录

```python
from exp_viewer import scan_directory

# 扫描目录，自动加载 fields.json（如果存在）
experiments = scan_directory(Path("my_experiments/"))

for exp in experiments:
    print(f"{exp.id}: accuracy = {exp.results['accuracy'].display_value}")
```

### 带项目标签扫描

```python
# 自定义项目标签
experiments = scan_directory(Path("my_experiments/"), project="cnn_sweep")
for exp in experiments:
    print(f"{exp.project}/{exp.id}")

# 默认使用目录名
experiments = scan_directory(Path("cnn_sweep/"))
# exp.project == "cnn_sweep"
```

### 加载单个实验

```python
from exp_viewer import register_from_directory

exp = register_from_directory(Path("my_experiments/run_001"))
print(exp.id)                     # "run_001"
print(exp.hyperparameters.keys()) # dict_keys(['learning_rate', ...])
print(exp.results['accuracy'].field_type)  # FieldType.PERCENTAGE
```

### 数据筛选与排序

```python
from exp_viewer import ExperimentSet

exp_set = ExperimentSet(experiments)

# 按字段排序
sorted_set = exp_set.sort_by("accuracy", descending=True)

# 筛选
filtered = exp_set.filter(lambda e: e.results["accuracy"].value > 0.9)

# 获取所有字段名
print(exp_set.all_hyperparameter_keys)
print(exp_set.all_result_keys)

# 转换为列式字典（可用于自定义绘图）
df = exp_set.to_dataframe()
print(df["res:accuracy"])  # [0.95, 0.88, 0.97]
print(df["project"])       # ["cnn_sweep", "cnn_sweep", ...]
```

### 字段值操作

```python
fv = exp.results["accuracy"]

fv.value          # 原始值: 0.95
fv.field_type     # FieldType.PERCENTAGE
fv.display_value  # 显示文本: "95.00%"
fv.numeric_value  # 归一化数值: 0.95
fv.sort_value     # 排序值: 0.95
```

### 导出 HTML

```python
from exp_viewer import export_html

# 自动生成默认图表
export_html(exp_set, "report.html", title="My Experiments")

# 自定义图表配置
export_html(
    exp_set,
    "custom_report.html",
    chart_configs=[
        {"type": "scatter", "x": "learning_rate", "y": "accuracy", "color": "optimizer"},
        {"type": "bar", "x": "id", "y": "loss"},
        {"type": "box", "y": "accuracy", "x": "optimizer"},
        {"type": "parallel_coordinates", "dimensions": ["learning_rate", "batch_size", "accuracy"]},
        {"type": "violin", "y": "accuracy", "x": "optimizer"},
        {"type": "heatmap", "x": "optimizer", "y": "batch_size", "size": "accuracy"},
    ],
)
```

### SQLite 存储

```python
from exp_viewer import Database

# 创建数据库
db = Database("experiments.db")

# 保存实验（project 字段自动持久化）
for exp in experiments:
    db.save(exp)

# 读取
exp_set = db.load_all()
single = db.load_by_id("run_001")

# 删除
db.delete("run_001")

# 清空
db.clear()

# 关闭
db.close()
```

### 字段类型推断

```python
from exp_viewer.schema import infer_type, infer_type_from_values
from exp_viewer.types import FieldType

# 单值推断
infer_type(0.95, "accuracy")  # FieldType.PERCENTAGE
infer_type(42, "batch_size")  # FieldType.NUMERIC
infer_type("adam")            # FieldType.STRING
infer_type(True)              # FieldType.BOOLEAN

# 跨值最小兼容类型
infer_type_from_values([0.01, 0.001], "lr")           # NUMERIC
infer_type_from_values([0.01, "auto"], "lr")           # STRING（NUMERIC + STRING → STRING）
infer_type_from_values([True, 1, 0], "flag")           # NUMERIC（BOOLEAN + NUMERIC → NUMERIC）
```

### 字段类型配置加载

```python
from exp_viewer.schema import load_fields_config
from pathlib import Path

config = load_fields_config(Path("my_experiments/"))
# {"accuracy": "percentage", "loss": "numeric", ...}
# 无 fields.json 时返回空 dict {}
```

---

## 静态 HTML 导出

导出的 HTML 文件特性：

- **自包含**：所有数据内嵌在 HTML 中，图表通过 Plotly.js CDN 渲染
- **标签页切换**：Table 标签页显示数据表格，Chart 标签页显示图表
- **无需服务端**：直接浏览器打开即可，可分享、可归档
- **默认图表**：自动选择合适的图表类型展示数据

### 自动图表选择规则

未指定 `chart_configs` 时，系统按以下规则生成默认图表：

1. 有结果指标时 → 第一个结果的柱状图（按实验 ID）
2. 有两个以上结果指标时 → 前两个指标的散点图
3. 同时有超参数和结果时 → 平行坐标图（最多 6 个超参数 + 3 个结果）
4. 有多个项目时 → 按项目分组的箱线图

### 自定义图表配置

通过 Python API 的 `chart_configs` 参数指定：

```python
export_html(
    exp_set,
    "report.html",
    chart_configs=[
        {
            "type": "scatter",
            "x": "learning_rate",
            "y": "accuracy",
            "color": "optimizer",
            "title": "Accuracy vs Learning Rate"
        },
        {
            "type": "box",
            "y": "accuracy",
            "x": "optimizer",
            "title": "Accuracy Distribution"
        },
        {
            "type": "violin",
            "y": "loss",
            "x": "optimizer",
        },
        {
            "type": "heatmap",
            "x": "optimizer",
            "y": "batch_size",
            "size": "accuracy",
        },
    ],
)
```

---

## SQLite 持久化

使用 `exp-viewer scan` 命令将实验数据存入 SQLite 数据库，后续可直接从数据库加载，跳过目录扫描。

### 数据库表结构

```sql
CREATE TABLE experiments (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    directory TEXT,     -- 存储项目标签（project label）
    created_at TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE hyperparameters (
    experiment_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value_text TEXT,
    value_type TEXT NOT NULL DEFAULT 'string',
    PRIMARY KEY (experiment_id, key)
);

CREATE TABLE results (
    experiment_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value_text TEXT,
    value_type TEXT NOT NULL DEFAULT 'string',
    PRIMARY KEY (experiment_id, key)
);
```

### 典型工作流

```bash
# 1. 扫描目录，存入数据库
exp-viewer scan my_experiments/ -o experiments.db

# 2. 从数据库启动服务（跳过扫描）
exp-viewer serve experiments.db

# 3. 从数据库导出报告
exp-viewer export experiments.db -o report.html

# 4. 查看数据库中的实验
exp-viewer info experiments.db
```

---

## 完整示例

以下是一个完整的实验管理流程：

### 1. 准备实验数据

```
ml_experiments/
├── fields.json
├── lr_001/
│   ├── config.json
│   └── results.json
├── lr_010/
│   ├── config.json
│   └── results.json
└── sgd_baseline/
    ├── config.json
    ├── results.json
    └── metadata.json
```

`fields.json`：
```json
{
    "learning_rate": "numeric",
    "batch_size": "numeric",
    "optimizer": "string",
    "use_augmentation": "boolean",
    "train_pct": "percentage",
    "accuracy": "percentage",
    "loss": "numeric",
    "f1_score": "percentage",
    "converged": "boolean",
    "epochs": "numeric"
}
```

`lr_001/config.json`：
```json
{
    "learning_rate": 0.001,
    "batch_size": 32,
    "optimizer": "adam",
    "use_augmentation": true,
    "train_pct": 0.8
}
```

`lr_001/results.json`：
```json
{
    "accuracy": 0.95,
    "loss": 0.032,
    "f1_score": 0.94,
    "converged": true,
    "epochs": 12
}
```

`lr_010/config.json`：
```json
{
    "learning_rate": 0.01,
    "batch_size": 64,
    "optimizer": "adam",
    "use_augmentation": false,
    "train_pct": 0.7
}
```

`lr_010/results.json`：
```json
{
    "accuracy": 0.88,
    "loss": 0.102,
    "f1_score": 0.86,
    "converged": false,
    "epochs": 50
}
```

`sgd_baseline/config.json`：
```json
{
    "learning_rate": 0.01,
    "batch_size": 32,
    "optimizer": "sgd",
    "use_augmentation": false,
    "train_pct": 0.8
}
```

`sgd_baseline/results.json`：
```json
{
    "accuracy": 0.82,
    "loss": 0.201,
    "f1_score": 0.80,
    "converged": false,
    "epochs": 50
}
```

`sgd_baseline/metadata.json`：
```json
{
    "id": "sgd_baseline",
    "name": "SGD Baseline",
    "tags": ["baseline", "sgd"]
}
```

### 2. 查看摘要

```bash
$ exp-viewer info ml_experiments/

Experiments: 3
Hyperparameter keys: learning_rate, batch_size, optimizer, use_augmentation, train_pct
Result keys: accuracy, loss, f1_score, converged, epochs

  [lr_001] lr_001
    hp.learning_rate = 0.0010
    hp.batch_size = 32
    hp.optimizer = adam
    hp.use_augmentation = True
    hp.train_pct = 80.00%
    res.accuracy = 95.00%
    res.loss = 0.0320
    res.f1_score = 94.00%
    res.converged = True
    res.epochs = 12

  [lr_010] lr_010
    hp.learning_rate = 0.0100
    hp.batch_size = 64
    hp.optimizer = adam
    hp.use_augmentation = False
    hp.train_pct = 70.00%
    res.accuracy = 88.00%
    res.loss = 0.1020
    res.f1_score = 86.00%
    res.converged = False
    res.epochs = 50

  [sgd_baseline] SGD Baseline
    tags: baseline, sgd
    hp.learning_rate = 0.0100
    hp.batch_size = 32
    hp.optimizer = sgd
    hp.use_augmentation = False
    hp.train_pct = 80.00%
    res.accuracy = 82.00%
    res.loss = 0.2010
    res.f1_score = 80.00%
    res.converged = False
    res.epochs = 50
```

### 3. 导出报告

```bash
$ exp-viewer export ml_experiments/ -o experiment_report.html
Exported 3 experiments to experiment_report.html
```

### 4. 持久化到数据库

```bash
$ exp-viewer scan ml_experiments/ -o ml_experiments.db
Scanned 3 experiments into ml_experiments.db
```

### 5. 启动交互式服务

```bash
# 单目录
$ exp-viewer serve ml_experiments/ --port 8050
Starting server at http://127.0.0.1:8050

# 多目录（跨项目对比）
$ exp-viewer serve ml_experiments/ transformer_experiments/ --labels CNN,Transformer
Starting server at http://127.0.0.1:8050
```

或从数据库启动：

```bash
$ exp-viewer serve ml_experiments.db --port 8050
Starting server at http://127.0.0.1:8050
```

### 6. 通过 API 获取数据

```bash
# 获取所有实验（含 project 字段）
curl http://127.0.0.1:8050/api/experiments

# 获取字段信息（含 visible 和 projects）
curl http://127.0.0.1:8050/api/fields

# 获取排序后的表格
curl "http://127.0.0.1:8050/api/table?sort_by=accuracy&sort_desc=true"

# 按项目筛选
curl "http://127.0.0.1:8050/api/table?project=CNN"

# 获取柱状图
curl "http://127.0.0.1:8050/api/chart/bar?x=id&y=accuracy"

# 获取散点图（按优化器着色）
curl "http://127.0.0.1:8050/api/chart/scatter?x=learning_rate&y=accuracy&color=optimizer"

# 获取箱线图
curl "http://127.0.0.1:8050/api/chart/box?y=accuracy&x=optimizer"

# 获取小提琴图
curl "http://127.0.0.1:8050/api/chart/violin?y=accuracy&x=optimizer"

# 获取散点图（按项目着色）
curl "http://127.0.0.1:8050/api/chart/scatter?x=learning_rate&y=accuracy&color=project"

# 筛选 accuracy > 0.85 的实验
curl "http://127.0.0.1:8050/api/table?filter_accuracy=gt:0.85"
```

### 7. 在 Python 中使用

```python
from exp_viewer import scan_directory, export_html, ExperimentSet
from pathlib import Path

# 加载数据（带项目标签）
experiments = scan_directory(Path("ml_experiments/"), project="cnn_sweep")
exp_set = ExperimentSet(experiments)

# 筛选 accuracy > 90% 的实验
good_exps = exp_set.filter(
    lambda e: e.results["accuracy"].value > 0.9
)
print(f"High accuracy experiments: {len(good_exps)}")

# 按损失排序
sorted_set = exp_set.sort_by("loss")

# 导出自定义报告
export_html(
    sorted_set,
    "low_loss_report.html",
    title="Experiments Sorted by Loss",
)

# 多项目对比
from exp_viewer.server.app import create_app
import uvicorn

roots = [
    (Path("cnn_experiments/"), "CNN"),
    (Path("transformer_experiments/"), "Transformer"),
]
app = create_app(experiments_roots=roots)
uvicorn.run(app, host="127.0.0.1", port=8050)
```

---

## 依赖

| 包 | 用途 |
|----|------|
| [FastAPI](https://fastapi.tiangolo.com/) | Web 服务端 |
| [Uvicorn](https://www.uvicorn.org/) | ASGI 服务器 |
| [Plotly](https://plotly.com/python/) | 图表渲染 |
| [Jinja2](https://jinja.palletsprojects.com/) | HTML 模板 |
| [orjson](https://github.com/ijl/orjson/) | JSON 解析 |

## License

MIT
