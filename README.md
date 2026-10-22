# RDK X5 YOLO11 Interface Study

《面向RDK X5平台的YOLO11输出接口、候选框恢复与CPU频率策略实测研究》的数据与代码归档。

**当前为作者私有审阅仓库。许可证和论文版本映射待确认；未改为公开仓库。** 所有测量均为既有实验证据，本次上传没有运行板端实验。

## 下载与复算

前往 **[Release v1.0.0-review](https://github.com/cty2489/rdkx5-yolo11-interface-study/releases/tag/v1.0.0-review)** 下载附件：

| 文件 | 字节 | 内容 |
|---|---:|---|
| rdkx5-yolo11-interface-study.zip | 223251415 | 完整归档，4106个文件，推荐用于完整核验与复算 |
| rdkx5-yolo11-interface-study_CODE.zip | 1401175 | 原冻结代码/说明包 |
| rdkx5-yolo11-interface-study_DATA.zip | 221850262 | data/，含逐帧记录、完整预测及排除批次 |
| SHA256SUMS.txt | — | 三个ZIP及归档清单的完整SHA256 |
| PACKAGE_RECEIPT.json | — | 原件保全、数值复算与ZIP校验回执 |

推荐下载完整ZIP，解压后运行：

```sh
python -m pip install -r analysis/requirements.txt
python analysis/make_tables.py
```

如果先克隆本仓库，再下载DATA.zip，把其中的`data/`放在仓库根目录，然后执行同一命令。离线复算不需要SSH、RDK SDK、模型或原视频。输出在`analysis/output/`；可用`--output <OUTPUT_DIR>`另存。

## 仓库内容

- [code/](code/)：按真实批次保留的C SDK桥接、M6/R/F/S/S2与CID NumPy消费者、worker及监控源码。私有路径只在副本中替换。
- [analysis/make_tables.py](analysis/make_tables.py)：只读CSV重算表和正文数值。
- [analysis/output/verification.json](analysis/output/verification.json)：17488项对照，数值差异0；Rev13可对应108项。
- [differences.md](analysis/output/differences.md)：给定Rev13共7表，请求的新表3—表10来自不同批次，未按旧编号混用。
- [DATA_DICTIONARY.md](DATA_DICTIONARY.md)、[CSV_COLUMNS.csv](CSV_COLUMNS.csv)：逐CSV每列定义、单位及统计约定。
- [models/MODEL_MANIFEST.csv](models/MODEL_MANIFEST.csv)：模型名、实际大小、SHA256；没有模型权重或BIN。
- [LICENSES.md](LICENSES.md)、[TO_CONFIRM.md](TO_CONFIRM.md)：许可证来源、已排除材料和作者待确认事项。本次未擅自授予MIT/Apache/CC许可。
- [ARCHIVE_README.md](ARCHIVE_README.md)：原冻结归档的完整环境、协议与限制说明，按整理时状态保留。

## 数据、校验与隐私

全部数据也放在本仓库的Release附件中，不依赖Zenodo，不要求DOI。普通Git树保留代码和小型说明；大数据留在Release附件。仓库当前私有，只有有权访问者可以下载。

数据覆盖Step2 A/B/C、E1/E2/E3/E4/E5/E6、Step0/Step1/E7。B中断48进程保留于`data/excluded/`，不进入本包统计。原始CSV行序和数值精度不变；4057个来源文件SHA未变。本次没有上传模型、原视频、COCO图像/标注原件、SDK二进制、密钥或授权不明helper内容。

`MANIFEST.csv`核验本仓库这次提交的文件（不含自身和.git）。`ARCHIVE_MANIFEST.csv`保留完整冻结归档的4105条记录；它用于核验Release完整ZIP解压内容，不用于核验新增的GitHub导航README。Release ZIP及原回执保持字节不变；仓库导航副本的改动不会伪装成原始文件。

## 发布状态与引用

作者确认代码/数据许可证及论文版本后，再决定是否把仓库改为Public。当前没有创建Zenodo记录或DOI；DOI不是使用本归档的前置条件。

引用题名：面向RDK X5平台的YOLO11输出接口、候选框恢复与CPU频率策略实测研究。作者、最终版本和正式引用信息待作者确认。
