# rdkx5-yolo11-interface-study

《面向RDK X5平台的YOLO11输出接口、候选框恢复与CPU频率策略实测研究》的离线数据与源码整理包。只整理已完成批次，本次新增板端连接、实验进程及模型前向均为0。该包尚待作者确认许可证、引用信息与论文版本映射，未上传或公开发布。

## 内容与目录

- `data/Step2_A`、`Step2_B_recovery08`、`Step2_C_full08`：最终8区组、8条件主对比，每视频64进程，三视频共192进程、90816条正式记录。
- `data/E1_*`频率扫描；`E2_A_v2`自由/30/15 FPS、30遍；`E3_*`配置分解；`E4_*_FSS2_12`候选恢复；`E5_A`独立重复批次；`E6_A`双角色流水线。只在各自批次内比较。
- `data/excluded/`：视频B原中断批次48进程，不用于任何本包论文复算。
- `data/Step0`：473帧F/S2功能核验与检测数组；`Step1`：R/F/S2/S各5000图预测、COCOeval数组及无损CSV视图；`E7`：同一既有FP32响应归档的两种NMS/cap重解码结果。
- `data/Step3`：频率驻留、进程CPU时间、分位数、FPS CI、重叠、governor参数和E2代码片段；它是同批源记录的既有离线提取，未产生新测量。
- `data/reference_rev13`、`paper_reference`：作者提供Rev13中旧批次的独立核对依据，不与新Step2混合。
- `code/`：按实际批次区分版本的项目C桥接、Python/NumPy消费者、worker、监控、计时及统计代码。`code/final/consumer.py`含M6/R/F/S/S2；`code/E3/consumer.py`保留CID_MAX/CID_INDEX。没有拼装一个从未执行过的“统一优化版本”。
- `analysis/make_tables.py`：只读本包CSV，复算指定表3—表10、正文指标及Rev13现有表3—表7，生成`analysis/output/verification.json`和`differences.md`。
- `models/`：模型身份和已证实的转换信息，无权重；`MANIFEST.csv`、`SOURCE_PROVENANCE.csv`、`REDACTION_LOG.csv`分别记录发布文件、源身份、脱敏副本差异。

## 实测环境与协议

RDK X5 V1.0，ARM64，Ubuntu 22.04.5；DNN Runtime 1.24.5、HBRT 3.15.55、Linux 6.1.83，NumPy 1.26.4、OpenCV 4.11.0。官方工具镜像：`openexplorer/ai_toolchain_ubuntu_20_x5_cpu:v1.2.8`。

D=schedutil 300–1500 MHz；O=ondemand 300–1500 MHz；L=userspace 1500 MHz；F600/F1200=userspace 600/1200 MHz。boost=0，继承允许核0–7，监控器nice19、核0、1 Hz。八核共享policy0，驻留表是一个共享policy累计计数映射到八核，并非八个独立计数器。BPU/DDR沿用各批冻结的governor/配置；不能把“设置未改变”改写成逐时刻硬件频率恒定。

串行计时：Pre=NV12读取和长度检查；SDK=输入复制、cache clean、提交/等待、输出invalidate、释放等外部调用包络，非纯BPU时间；Post=输出读取、分类/恢复、DFL坐标、NMS与结果组织；Total=输入读取开始至结果可用。E6是流水线的queue-inclusive latency和独立stream FPS，阶段可在墙钟上重叠。E2 sleep在frame_step之前，t0在sleep之后，Total不包含sleep。普通计时每进程完整预热一遍、正式三遍；E2正式30遍；质量验证不套用计时遍数。

## 离线复现

1. 保持该根目录名称；若数据与代码分ZIP发布，解压到同一个根目录。
2. 在独立Python环境安装`analysis/requirements.txt`所列依赖。无需SSH、SDK、模型或视频。
3. 运行`python analysis/make_tables.py`。脚本只读取`data/`下CSV，不执行任意实验源码；新输出位于`analysis/output/`。如需保护本包已生成结果，使用`--output <OUTPUT_DIR>`。
4. 检查`verification.json`、`comparison_checks.csv`和`differences.md`。新表号与作者提供Rev13的表号不是同一版本映射；范围差异不隐去，不把旧批次数字与新批次作差。
5. 校验`MANIFEST.csv`：逐文件读取相对路径、bytes和SHA256。清单不包含自身，避免自引用；清单本身的SHA256在ZIP旁交付回执中给出。

板端源码只供审查和后续获得授权时复现实验：需要合法取得精确哈希的模型和视频、厂商SDK及设备权限；按对应批次`protocol_frozen.json`恢复资源映射，使用对应C桥接编译。不得运行本包脚本来自动启动新批次。本包没有完整可再现原始量化编译链的全部证据，不能保证从任意新下载权重重编出相同BIN。

## 副本脱敏

所有替换仅发生于副本：私有工程路径、用户名、IP、内部链接变为占位符或相对路径。`<PROJECT_ROOT>`、`<SOURCE_WORKSPACE>`、`<HOME>`、`<BOARD_PROJECT>`、`<BOARD_ASSETS>`分别表示自定义资源根；`<SYS_ROOT>`、`<PROC_ROOT>`、`<USR_ROOT>`、`<ETC_ROOT>`、`<DEV_ROOT>`等表示标准OS路径根。原始路径关系保留在可公开的后缀中，私人前缀不提供。Python shebang或字符串也可能替换，因此板端历史源码在恢复占位根之前不是一键运行脚本；恢复根映射属于部署配置，不改变算法。源文件SHA256和脱敏后SHA256均记录。逐帧数值单元格逐个核对，行/列序不变；源码AST除字符串字面量外一致。变量名`token`若出现在watchdog中代表进程启动时刻标识，非认证令牌。

不含密钥、口令、SDK/工具链二进制、厂商头文件、COCO图像、三视频原文件、PT/ONNX/BIN、原论文DOCX。COCO标注仅提供来源与哈希，不随包重复分发。无许可证来源不明的第三方评测helper内容；见`TO_CONFIRM.md`。

## 许可证、引用与限制

本次不擅自授予MIT、Apache-2.0或CC许可。项目自编代码建议MIT或Apache-2.0，实验数据建议CC BY 4.0，均待权利人确认；涉及Ultralytics的派生代码/模型另受其许可约束，不能统一改标MIT。第三方结论及官方来源在`LICENSES.md`。在作者确认之前，本ZIP为审阅候选，不能宣称已按建议许可证公开。

引用建议：`作者待确认. 面向RDK X5平台的YOLO11输出接口、候选框恢复与CPU频率策略实测研究：数据与代码[数据集/软件]. 版本1，2026. <URL>，<DOI>`。未虚构作者、发表信息或DOI。

已知限制：三段视频尚无公开许可；缺少它们时可完整复算已存计时，但不能重做输入相同的板端前向。厂商SDK内部节点时间、缓存层级命中、每帧线程迁移不是本包测量。E7只保留每位置获胜类，不等同Ultralytics默认multi-label评测。S2使用每个尺度一次np.take，三尺度不是同一物理buffer。不同批次、SDK调用模式、频率策略不合并扩大n。标准SD为独立进程均值的样本SD；CI为配对独立区组差值的Student t区间。

原报告中指向本次未选择的图件、内部完整回执或旧绝对路径的链接，在副本中改成未附说明；科学数值不变。该排版替换与脱敏一起列入副本哈希，原件不改。
