# 建议发布拆分

本轮只制作本地候选包，不创建仓库、Zenodo记录或DOI。

1. `rdkx5-yolo11-interface-study_CODE.zip`包含README、分析/统计代码、模型身份、许可证清单、列字典、复算输出和完整MANIFEST，拟放GitHub；不将data/提交普通Git历史。
2. `rdkx5-yolo11-interface-study_DATA.zip`只包含data/，拟作为Zenodo数据附件；与CODE解压至同一根目录后运行analysis/make_tables.py。
3. `rdkx5-yolo11-interface-study.zip`是完整本地交付。若超过100 MB，不作为Git普通单文件提交。GitHub官方普通Git单文件硬限制为100 MiB；本次同时报告十进制MB与MiB，遵照作者100 MB阈值保守拆分。
4. 作者先确认许可证、视频排除、作者署名和论文版本映射，再建立Zenodo记录，取得真实DOI，替换<DOI>和<URL>。数据记录与GitHub版本互链；DOI应指数据/软件记录，不冒充论文DOI。

依据：[GitHub大文件说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github?platform=windows)；[Zenodo建档说明](https://help.zenodo.org/docs/deposit/create-new-upload/)。当前DOI=未创建。
