# 许可证核查与待作者确认

核查日期：2026-10-22。本文件是来源核查和建议，不代作者作许可授权，不上传材料。

|材料|核查结果|本包处理|需确认|
|---|---|---|---|
|项目自编C桥接、NumPy消费者、worker、监测与统计脚本|项目实验证据中的源代码；没有据此替作者选择公开许可证|源代码副本、原哈希、脱敏哈希，按批次区分|权利人/机构归属；MIT或Apache-2.0选择；是否含第三方改编|
|新增离线复算/整理脚本与自有实验数值|许可证由作者决定；建议代码MIT/Apache-2.0、数据CC BY 4.0|候选副本；尚未授予上述许可|同上|
|Ultralytics YOLO11代码/权重|官方仓库为AGPL-3.0，厂商另提供Enterprise许可；官方页面将训练模型也列入默认AGPL范围|不含Ultralytics库和任何权重/BIN；仅模型哈希和官方获取地址|确认具体版本与派生关系；不能给相关派生物统一改标MIT|
|D-Robotics rdk_model_zoo公开仓库代码|官方仓库LICENSE为Apache-2.0|未直接打包厂商仓库、头文件或动态库|若以后加入，保留相应NOTICE与许可证|
|D-Robotics工具链v1.2.8、Runtime/HBRT及编译BIN|未取得与本次精确版本相匹配的授权文本；不能以model_zoo的Apache许可证代替工具链或BIN条款，也不能把J6协议套到X5|仅记录镜像名、版本、命令和模型身份；不含工具链/SDK/BIN|从合法取得的镜像/SDK随附条款核验使用与再分发权限；BIN还受模型来源许可约束|
|COCO标注/网站|COCO Consortium官方Terms of Use：CC BY 4.0|只提供标注文件SHA256及官方下载说明|如以后分发标注须署名并保留许可|
|COCO图像|版权不归COCO Consortium统一所有；按原Flickr条款及每图许可|不含图像|不得把所有COCO图片概括为CC BY 4.0|
|A/B/C视频|来源与公开许可未确定|不含原视频或图像；仅文件名、哈希、衍生数值|作者确认是否有权公开；本次未发布|
|原SDK评测helper、未知授权头文件/二进制、历史私有连接控制器|没有足以确认再分发的逐文件许可证/来源|不入包，仅TO_CONFIRM登记或获取说明|确认后才能加入；不能从SDK API可调用推导可再分发|

官方核查来源：

- [Ultralytics许可证](https://www.ultralytics.com/license)及[官方LICENSE](https://github.com/ultralytics/ultralytics/blob/main/LICENSE)。
- [D-Robotics model_zoo LICENSE](https://github.com/D-Robotics/rdk_model_zoo/blob/main/LICENSE)。该许可范围不可扩展推断至SDK/工具链。
- [D-Robotics工具链官方文档入口](https://toolchain.d-robotics.cc/guide/doc_introduction.html)列有授权协议；精确X5 v1.2.8适用文本本轮未确认。直接协议页取回失败一次，未反复网络诊断；不以其他产品协议补证。
- [COCO官方Terms of Use源码](https://github.com/cocodataset/cocodataset.github.io/blob/master/dataset/termsofuse.htm)与[下载入口](https://cocodataset.org/#download)。
