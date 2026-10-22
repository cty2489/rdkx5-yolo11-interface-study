# 模型身份、转换与获取

MODEL_MANIFEST.csv仅列文件名、实际大小和SHA256，所有权重文件均未包含。F、S、S2使用同一修改BIN。官方YOLO11来源：[Ultralytics模型文档](https://docs.ultralytics.com/models/yolo11/)，须遵守相应许可；新下载权重不保证产生本次相同BIN。

已证实的R→F官方命令（镜像openexplorer/ai_toolchain_ubuntu_20_x5_cpu:v1.2.8，输入只读、输出独立、容器无网络）：

```sh
hb_model_modifier <INPUT_ROOT>/yolov11n_x5_1.bin -r bbox0_HzDequantize -r bbox1_HzDequantize -r bbox2_HzDequantize -o <OUTPUT_ROOT>/m9_bbox_native.bin
```

仅三个bbox节点移除，score/class路径保留；量化恢复与stride来自实测ABI清单。输入640×640 NV12，每帧614400字节，模型输入/CPU坐标映射来自冻结协议；阈值0.3、IoU 0.5用于视频计时，COCO另用0.001与类别感知NMS、max100。

M6/R/CID源模型初次编译的全部命令、校准文件和参数未形成可以证明其精确SHA产物的完整链。本包不伪造缺失步骤，也不把旧NHWC候选的hb_mapper配置冒充NCHW M9编译记录。若需重编，应先取得并核验原链；本次不编译任何模型。

C桥接源文件包含对厂商SDK API的调用，不随包附SDK库/头文件。须由获授权的板端SDK安装提供dnn/hb_dnn.h、dnn/hb_sys.h和libdnn等。示意编译命令（不是历史已核实的完整编译回执）：`cc -shared -fPIC -O2 code/final/p1_bridge.c -o <BUILD_ROOT>/libbaselinebridge.so -ldnn`；头文件和库搜索路径需按实际SDK配置，不启用fast-math。
