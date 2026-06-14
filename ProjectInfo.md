下面这份文档可以直接丢给 Claude Code、Cursor Agent、OpenAI Codex、Trae、Augment 等 AI Agent 作为项目需求文档。

---

# 图片去背景与自动切图工具

## 项目概述

开发一个独立运行的 Windows 桌面工具，用于批量处理游戏美术资源。

工具主要功能：

1. 自动去除图片背景
2. 自动切分图集中的独立元素
3. 导出透明 PNG
4. 导出切图配置数据
5. 支持批量处理

目标是替代部分 Photoshop 去背景功能以及 Unity Sprite Editor 的 Automatic Slice 功能。

工具不依赖 Unity，最终输出为独立 exe。

---

# 技术方案

## 开发语言

Python 3.12+

---

## GUI框架

PySide6

原因：

* 原生桌面GUI
* 现代化界面
* 支持图片预览
* 支持拖拽
* 支持表格和树形结构
* AI Agent生成代码成熟

---

## 图像处理

### OpenCV

用于：

* Alpha检测
* 连通区域分析
* Bounding Box生成
* 自动切图

---

### Pillow

用于：

* 图片读取
* PNG导出
* 图片缩放预览

---

## AI去背景

### 第一阶段

使用 rembg

底层模型：

```text
u2net
```

功能：

```text
输入图片
↓
AI识别主体
↓
生成透明PNG
```

---

### 第二阶段（预留）

支持切换：

```text
BiRefNet
SAM2
RMBG-2.0
```

作为高级模式

---

## 打包方案

PyInstaller

生成：

```text
ImageTool.exe
```

用户无需安装Python环境

---

# 项目结构

```text
ImageTool/

├─ main.py

├─ ui/
│   ├─ main_window.py
│   ├─ image_view.py
│   ├─ preview_widget.py

├─ core/
│   ├─ background_remove.py
│   ├─ sprite_slicer.py
│   ├─ image_loader.py
│   ├─ batch_processor.py

├─ export/
│   ├─ png_exporter.py
│   ├─ json_exporter.py

├─ resources/
│   ├─ icons/

├─ output/

└─ requirements.txt
```

---

# GUI设计

## 主界面

```text
┌──────────────────────────────────────┐
│ 菜单栏                               │
├──────────────────────────────────────┤
│                                      │
│         图片预览区域                 │
│                                      │
│                                      │
├──────────────────────────────────────┤
│ 导入图片                             │
│ 导入文件夹                           │
│ 去背景                               │
│ 自动切图                             │
│ 导出结果                             │
├──────────────────────────────────────┤
│ 参数区域                             │
└──────────────────────────────────────┘
```

---

# 功能需求

## 功能1：导入图片

支持：

```text
png
jpg
jpeg
webp
bmp
```

支持：

* 单文件导入
* 多文件导入
* 文件夹导入
* 拖拽导入

---

## 功能2：AI去背景

### 流程

```text
原图
↓
rembg
↓
透明PNG
```

### 输出

```text
xxx_removed.png
```

### 支持

批量处理

---

## 功能3：自动切图

类似：

Unity Sprite Editor

Automatic Slice

---

### 算法流程

#### Step1

获取Alpha通道

```python
alpha = image[:, :, 3]
```

---

#### Step2

阈值处理

```python
mask = alpha > threshold
```

默认：

```text
threshold = 10
```

---

#### Step3

查找连通区域

```python
cv2.connectedComponents
```

或

```python
cv2.findContours
```

---

#### Step4

生成Bounding Box

例如：

```text
对象A

x=120
y=50
w=64
h=64
```

---

#### Step5

过滤小碎片

参数：

```text
Min Area
```

默认：

```text
64 px
```

---

#### Step6

扩展Padding

例如：

```text
Padding = 4
```

结果：

```text
原边界:
64×64

导出:
72×72
```

---

#### Step7

导出PNG

```text
sprite_001.png
sprite_002.png
sprite_003.png
```

---

# 功能4：切图预览

切图完成后显示：

```text
┌─────┐
│ 01  │
└─────┘

┌─────┐
│ 02  │
└─────┘
```

并在原图上绘制：

```text
Bounding Box
```

---

# 功能5：参数面板

## Alpha阈值

默认：

```text
10
```

范围：

```text
0~255
```

---

## 最小面积

默认：

```text
64
```

单位：

```text
像素
```

---

## Padding

默认：

```text
4
```

---

## 合并邻近区域

布尔值：

```text
True
False
```

---

## 导出命名

支持：

```text
sprite_001
sprite_002

或者

文件名_001
文件名_002
```

---

# 导出结构

## PNG导出

```text
output/

├─ source_removed.png

├─ sprites/
│   ├─ sprite_001.png
│   ├─ sprite_002.png
│   └─ sprite_003.png
```

---

## JSON导出

```json
{
  "sprites": [
    {
      "name": "sprite_001",
      "x": 120,
      "y": 50,
      "width": 64,
      "height": 64
    }
  ]
}
```

---

# 批量处理

支持：

```text
输入目录
↓
遍历全部图片
↓
自动去背景
↓
自动切图
↓
导出结果
```

输出：

```text
Output/

├─ Hero/
│   ├─ Hero_001.png
│   └─ Hero.json

├─ Monster/
│   ├─ Monster_001.png
│   └─ Monster.json
```

---

# 后续扩展需求

## V2

手动编辑切图框

类似：

Unity Sprite Editor

---

## V3

智能切图

使用：

```text
SAM2
GroundingDINO
BiRefNet
```

支持：

* 粘连目标拆分
* 多角色自动识别
* UI图标自动拆分

---

## V4

图集生成

支持：

```text
多个PNG
↓
自动Packing
↓
Atlas.png
Atlas.json
```

类似：

TexturePacker

---

# 验收标准

### 去背景

* 单张图片处理成功率 ≥95%
* 支持批量处理

### 自动切图

* 正确识别透明区域
* 正确生成Bounding Box

### 导出

* PNG透明通道保留
* JSON数据正确

### 打包

* 生成独立 exe
* 无需安装 Python 环境

### 性能目标

```text
1024×1024图片

去背景：
< 3秒

自动切图：
< 0.5秒
```

这份需求已经足够让 AI Agent 直接开始生成完整项目了。后续如果你准备做成长期使用的美术工具，我还建议增加一个 **“Photoshop 风格图层面板 + SpriteEditor 风格切图编辑器”**，这样实用性会提升一个档次。
