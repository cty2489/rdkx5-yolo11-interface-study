# 源码版本

按批次保留真实冻结源码，不把不同版本合并冒充曾执行过的版本。`final/`用于最终Step0/1/2，`E1/`、`E2/`、`E3/`、`E4/`、`E6/`各自对应源批次；E5复用E3同一统一框架。逐文件SHA在SOURCE_VERSIONS.csv与SOURCE_PROVENANCE.csv，最终源冻结提交见source_freeze_receipt.json（不是公开仓库提交或DOI）。

`final/consumer.py`包含M6、R、F、S、S2；E3版本增加CID两路径。C桥接与NumPy stride视图保留原实现。所有路径替换都仅在副本字符串/注释中，不更改计时边界或算法。恢复占位根和合法SDK/模型/输入之前，历史worker不是一键运行程序；当前可直接执行的是analysis/make_tables.py离线复算。

未包含第三方库、SDK头文件/.so、Ultralytics权重或授权来源不明的rdk_x5_yolo11_9head_eval.py。后者仍可能由历史源码import；许可证与来源确认前不能补入。后续若要再跑板端，须先获得合法依赖、精确资源和新的设备实验授权。本次没有运行这些worker。

common_p1/保留E1/E2/E3/E6引用的原始公共依赖；其p1_process.py的源SHA为e1963837396aebe4beecd02a279ba369a25f3f142f8f90605c924e255faf5d25，不能用final/中的后续版本替代。
