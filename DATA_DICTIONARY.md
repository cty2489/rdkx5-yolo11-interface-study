# DATA_DICTIONARY

## 总则

时间差Δ(X→Y)=T_X−T_Y，正值表示Y更快。样本SD使用独立进程均值，分母n−1。CI先在同一冻结区组内配对作差，再以区组为统计单位：d̄±t(0.975,n−1)·s_d/√n，df=n−1。每帧、视频三遍不是独立统计重复。FPS新增表用FPS_Y−FPS_X，正值表示Y吞吐更高；原归档FPS左−右表保留direction说明，不改原数。

D=schedutil 300–1500 MHz，O=ondemand 300–1500 MHz，L=userspace固定1500 MHz，F600/F1200=userspace固定600/1200 MHz。CPU% = 100·(Δuser+Δsys)/Δwall；100%对应一个核，多线程可超过100%。formal与whole_reaped_process分子分母各自配套；E2 formal窗口包含sleep。系统<PROC_ROOT>/stat utilization_percent是另一口径，不能当进程CPU%。

平均频率=Σ(f_MHz·Δticks)/ΣΔticks；time_in_state USER_HZ=100。CPU0–7共享policy0，表中重复映射不是独立逐核测量。phase=formal与per_pass窗口重叠，不能相加。空白、NA、-1评价缺失不改为0。逐帧分位数为NumPy linear合并帧描述。所有源CSV行序和数值字符串保留；公开副本只做文本脱敏。

E6的SDK envelope与CPU post service是墙钟区间，不等于纯BPU执行或线程CPU占用；其交集并非硬件级节点profiling。Total含排队；Post不含QueueWait。E2 t0在sleep之后，Total不含限帧等待。

## 每文件每列对应

`CSV_COLUMNS.csv`逐一列出1356个CSV的每一列，共41276项，包含有序列号、定义和单位；`CSV_SCHEMA_INDEX.csv`列出完整文件列表和schema。下表为复用字段定义，不省略CSV_COLUMNS中的逐文件映射。两张索引自身列：csv_path=相对路径，ordinal=从1开始的列号，column=原列名，definition=定义文本，unit=单位文本，schema=有序表头SHA派生编号，columns=列数。MANIFEST列path=包内相对路径、bytes=长度、sha256=完整哈希；它不包含自身。

|列名|定义|单位|
|---|---|---|
|AP|标准COCO检测AP/AR；AP50/75对应IoU，s/m/l对应目标面积；AR后缀1/10/100是COCO maxDets|0–1|
|AP50|标准COCO检测AP/AR；AP50/75对应IoU，s/m/l对应目标面积；AR后缀1/10/100是COCO maxDets|0–1|
|AP75|标准COCO检测AP/AR；AP50/75对应IoU，s/m/l对应目标面积；AR后缀1/10/100是COCO maxDets|0–1|
|APl|标准COCO检测AP/AR；AP50/75对应IoU，s/m/l对应目标面积；AR后缀1/10/100是COCO maxDets|0–1|
|APm|标准COCO检测AP/AR；AP50/75对应IoU，s/m/l对应目标面积；AR后缀1/10/100是COCO maxDets|0–1|
|APs|标准COCO检测AP/AR；AP50/75对应IoU，s/m/l对应目标面积；AR后缀1/10/100是COCO maxDets|0–1|
|AR1|标准COCO检测AP/AR；AP50/75对应IoU，s/m/l对应目标面积；AR后缀1/10/100是COCO maxDets|0–1|
|AR10|标准COCO检测AP/AR；AP50/75对应IoU，s/m/l对应目标面积；AR后缀1/10/100是COCO maxDets|0–1|
|AR100|标准COCO检测AP/AR；AP50/75对应IoU，s/m/l对应目标面积；AR后缀1/10/100是COCO maxDets|0–1|
|ARl|标准COCO检测AP/AR；AP50/75对应IoU，s/m/l对应目标面积；AR后缀1/10/100是COCO maxDets|0–1|
|ARm|标准COCO检测AP/AR；AP50/75对应IoU，s/m/l对应目标面积；AR后缀1/10/100是COCO maxDets|0–1|
|ARs|标准COCO检测AP/AR；AP50/75对应IoU，s/m/l对应目标面积；AR后缀1/10/100是COCO maxDets|0–1|
|CI95_high|该行FPS均值、样本SD、双侧Student t区间端点或原始区组差值，按列名区分|frame/s|
|CI95_low|该行FPS均值、样本SD、双侧Student t区间端点或原始区组差值，按列名区分|frame/s|
|CI_estimand|置信区间估计目标说明|文本|
|CPU_one_core_percent|100×进程(user+sys)CPU秒/同窗口wall秒；100%为一个核；多线程可超过100%；pooled为先加分子分母，process_mean为各进程比值均值|% of one core|
|CPU_percent|列名前缀所定义的百分比，具体分子分母见本行stage/contrast与DATA_DICTIONARY总则|%|
|CPU_percent_pooled|100×进程(user+sys)CPU秒/同窗口wall秒；100%为一个核；多线程可超过100%；pooled为先加分子分母，process_mean为各进程比值均值|% of one core|
|CPU_percent_process_mean|100×进程(user+sys)CPU秒/同窗口wall秒；100%为一个核；多线程可超过100%；pooled为先加分子分母，process_mean为各进程比值均值|% of one core|
|CPU_percent_sample_SD|100×进程(user+sys)CPU秒/同窗口wall秒；100%为一个核；多线程可超过100%；pooled为先加分子分母，process_mean为各进程比值均值|% of one core|
|CPU_post_service_ns|逐进程CPU后处理[t_post_start,t_final)服务区间累计或其配置均值/SD；是墙钟服务区间而非线程CPU时长|ns或s，按后缀|
|CPU_post_service_seconds|逐进程CPU后处理[t_post_start,t_final)服务区间累计或其配置均值/SD；是墙钟服务区间而非线程CPU时长|ns或s，按后缀|
|CPU_post_service_seconds_mean|逐进程CPU后处理[t_post_start,t_final)服务区间累计或其配置均值/SD；是墙钟服务区间而非线程CPU时长|ns或s，按后缀|
|CPU_post_service_seconds_sample_SD|逐进程CPU后处理[t_post_start,t_final)服务区间累计或其配置均值/SD；是墙钟服务区间而非线程CPU时长|ns或s，按后缀|
|CPU_ratio|进程(user+sys)CPU秒/同窗口wall秒；未乘100|比值，1=一核|
|CPU_ratio_pooled|进程(user+sys)CPU秒/同窗口wall秒；未乘100|比值，1=一核|
|ConsumerUnclassified_ms|已测阶段与分阶段和之间的记账余项；保留原浮点正负舍入值|ms|
|Consumer_ms|输出访问结束至CPU消费者结果完成|ms|
|DFLCoordinates_ms|公共DFL解码及坐标恢复|ms|
|FPS|正式帧数/明确记录的墙钟窗口或stream区间；E6 FPS用stream首t0至末t_final，不能用1000/平均latency替代|frame/s|
|FPS_contrast|有序配置对；时间Δ=X−Y；原归档FPS表若direction指left更快则为FPS左−右，新增FPS表明确right−left|代号|
|FPS_mean|正式帧数/明确记录的墙钟窗口或stream区间；E6 FPS用stream首t0至末t_final，不能用1000/平均latency替代|frame/s|
|FPS_right_minus_left|右配置FPS−左配置FPS；正值表示右侧吞吐更高，区别于时间左−右符号|frame/s|
|FPS_sample_SD|正式帧数/明确记录的墙钟窗口或stream区间；E6 FPS用stream首t0至末t_final，不能用1000/平均latency替代|frame/s|
|ForwardSync_ms|同步forward外部调用包络，非硬件纯BPU时长|ms|
|InputPrepare_ms|SDK输入prepare外部包络|ms|
|K|该帧通过阈值的三尺度候选位置数|位置|
|K_mean|每独立进程正式帧平均候选数|位置/帧|
|NMSAssemble_ms|公共NMS及最终数组组织|ms|
|NMS_IoU|NMS所用IoU阈值，不是COCOeval平均IoU阈值|0–1|
|OutputAccess_ms|SDK输出buffer映射/NumPy视图访问耗时|ms|
|P50_ms|按列名所示阶段的正式逐帧linear分位数；配置级为合并帧描述，不作独立重复|ms|
|P95_ms|按列名所示阶段的正式逐帧linear分位数；配置级为合并帧描述，不作独立重复|ms|
|P99_ms|按列名所示阶段的正式逐帧linear分位数；配置级为合并帧描述，不作独立重复|ms|
|PID|内核进程ID，非账号|PID|
|Post_P50_ms|按列名所示阶段的正式逐帧linear分位数；配置级为合并帧描述，不作独立重复|ms|
|Post_P95_ms|按列名所示阶段的正式逐帧linear分位数；配置级为合并帧描述，不作独立重复|ms|
|Post_P99_ms|按列名所示阶段的正式逐帧linear分位数；配置级为合并帧描述，不作独立重复|ms|
|Post_mean_ms|列名前缀阶段的逐进程正式帧均值|ms|
|Post_ms|从输出访问开始至完整检测结果可用的CPU后处理服务时间；E6不含排队等待|ms|
|Pre_P50_ms|按列名所示阶段的正式逐帧linear分位数；配置级为合并帧描述，不作独立重复|ms|
|Pre_P95_ms|按列名所示阶段的正式逐帧linear分位数；配置级为合并帧描述，不作独立重复|ms|
|Pre_P99_ms|按列名所示阶段的正式逐帧linear分位数；配置级为合并帧描述，不作独立重复|ms|
|Pre_mean_ms|列名前缀阶段的逐进程正式帧均值|ms|
|Pre_ms|读取NV12帧与长度校验的墙钟耗时|ms|
|QueueWait_P50_ms|按列名所示阶段的正式逐帧linear分位数；配置级为合并帧描述，不作独立重复|ms|
|QueueWait_P95_ms|按列名所示阶段的正式逐帧linear分位数；配置级为合并帧描述，不作独立重复|ms|
|QueueWait_P99_ms|按列名所示阶段的正式逐帧linear分位数；配置级为合并帧描述，不作独立重复|ms|
|QueueWait_mean_ms|列名前缀阶段的逐进程正式帧均值|ms|
|QueueWait_ms|E6 forward完成至CPU后处理服务开始的队列等待|ms|
|RestoreGather_ms|恢复/候选组织：R浮点候选提取、F全量恢复+候选提取、S/S2候选整数取数+恢复+组织|ms|
|Rev13_corresponding_table|请求表编号、对应Rev13表号、来源批次或版本/范围匹配状态，按列名区分|编号/标识|
|SDK_CPU_intersection_ns|SDK包络区间集合与CPU后处理服务区间集合的交集长度累计/配置均值或SD；不是纯BPU硬件重叠|ns或s，按后缀|
|SDK_CPU_intersection_seconds_mean|SDK包络区间集合与CPU后处理服务区间集合的交集长度累计/配置均值或SD；不是纯BPU硬件重叠|ns或s，按后缀|
|SDK_CPU_intersection_seconds_sample_SD|SDK包络区间集合与CPU后处理服务区间集合的交集长度累计/配置均值或SD；不是纯BPU硬件重叠|ns或s，按后缀|
|SDK_CPU_overlap_seconds_mean|列名前缀指定的进程/线程user、sys或wall时间；formal/per_pass/whole窗口严格分开，sum为先合计，mean为独立进程均值|s|
|SDK_CPU_post_envelope_overlap_seconds|SDK包络区间集合与CPU后处理服务区间集合的交集长度累计/配置均值或SD；不是纯BPU硬件重叠|ns或s，按后缀|
|SDK_CPU_union_ns|SDK包络和CPU服务区间集合并集长度=SDK累计+CPU累计−交集|ns或s，按后缀|
|SDK_CPU_union_seconds_mean|SDK包络和CPU服务区间集合并集长度=SDK累计+CPU累计−交集|ns或s，按后缀|
|SDK_CPU_union_seconds_sample_SD|SDK包络和CPU服务区间集合并集长度=SDK累计+CPU累计−交集|ns或s，按后缀|
|SDK_P50_ms|按列名所示阶段的正式逐帧linear分位数；配置级为合并帧描述，不作独立重复|ms|
|SDK_P95_ms|按列名所示阶段的正式逐帧linear分位数；配置级为合并帧描述，不作独立重复|ms|
|SDK_P99_ms|按列名所示阶段的正式逐帧linear分位数；配置级为合并帧描述，不作独立重复|ms|
|SDK_envelope_ns|逐进程所有SDK外部墙钟包络[t_read,t_forward)长度累计或其配置均值/SD|ns或s，按后缀|
|SDK_envelope_percent_stream_mean|100×SDK包络累计长度/stream长度：独立进程比值均值、其样本SD或先合计分子分母的pooled比值，按列名区分|%|
|SDK_envelope_percent_stream_pooled|100×SDK包络累计长度/stream长度：独立进程比值均值、其样本SD或先合计分子分母的pooled比值，按列名区分|%|
|SDK_envelope_percent_stream_sample_SD|100×SDK包络累计长度/stream长度：独立进程比值均值、其样本SD或先合计分子分母的pooled比值，按列名区分|%|
|SDK_envelope_seconds|逐进程所有SDK外部墙钟包络[t_read,t_forward)长度累计或其配置均值/SD|ns或s，按后缀|
|SDK_envelope_seconds_mean|逐进程所有SDK外部墙钟包络[t_read,t_forward)长度累计或其配置均值/SD|ns或s，按后缀|
|SDK_envelope_seconds_sample_SD|逐进程所有SDK外部墙钟包络[t_read,t_forward)长度累计或其配置均值/SD|ns或s，按后缀|
|SDK_mean_ms|列名前缀阶段的逐进程正式帧均值|ms|
|SDK_ms|输入复制/cache clean/提交等待/输出invalidate及任务释放的外部SDK调用包络，非纯BPU时间|ms|
|Select_ms|分类响应处理、阈值筛选和候选索引生成；包含各配置必要分类消费差异|ms|
|Total_P50_ms|按列名所示阶段的正式逐帧linear分位数；配置级为合并帧描述，不作独立重复|ms|
|Total_P95_ms|按列名所示阶段的正式逐帧linear分位数；配置级为合并帧描述，不作独立重复|ms|
|Total_P99_ms|按列名所示阶段的正式逐帧linear分位数；配置级为合并帧描述，不作独立重复|ms|
|Total_includes_pacing_sleep|E2布尔定义项，按列名区分|0/1|
|Total_mean_ms|列名前缀阶段的逐进程正式帧均值|ms|
|Total_ms|t_final−t0；串行为完整端到端，E6含QueueWait，E2不含此前sleep|ms|
|Unclassified_ms|已测阶段与分阶段和之间的记账余项；保留原浮点正负舍入值|ms|
|absolute_difference|验证范围、检查项、复算值、参照值、绝对差、容许舍入误差或对账布尔项，按列名区分|随所检查指标；equal为0/1|
|access|资源类别、身份核验来源、获取/权利说明或源文件类别，按列名区分|文本|
|affected_cpus|允许CPU亲和性列表或cpufreq共享策略覆盖核列表，按列名区分|核号列表|
|affinity|允许CPU亲和性列表或cpufreq共享策略覆盖核列表，按列名区分|核号列表|
|allowed_cores|允许CPU亲和性列表或cpufreq共享策略覆盖核列表，按列名区分|核号列表|
|area|COCOeval张量零基轴索引；分别0.50:0.05:0.95、0:0.01:1、标准80类、all/s/m/l、1/10/100；详见Step1/TENSOR_CSV.md|索引|
|arrival_to_result_ms|E2相对预定release的完成延迟；free-run等于Total|ms|
|asset|资源类别、身份核验来源、获取/权利说明或源文件类别，按列名区分|文本|
|batch|冻结批次标识；批次之间不合并统计|标识|
|block|独立区组编号，从1开始|区组|
|block_1|该列所标独立区组的FPS右−左差值|frame/s|
|block_2|该列所标独立区组的FPS右−左差值|frame/s|
|block_3|该列所标独立区组的FPS右−左差值|frame/s|
|block_4|该列所标独立区组的FPS右−左差值|frame/s|
|block_5|该列所标独立区组的FPS右−左差值|frame/s|
|block_6|该列所标独立区组的FPS右−左差值|frame/s|
|boundary|边界采样点或角色begin/end|代号|
|boundary_records|该参数值所对应的原边界记录数|条|
|busy_ticks|<PROC_ROOT>/stat或task stat的user/system/total/busy计数或完整差值向量，按列名区分|USER_HZ tick|
|busy_wait|E2布尔定义项，按列名区分|0/1|
|bytes|原件/包内文件长度，按列名区分|byte|
|candidate_bin|按候选数量划分的描述性区间，原标签不改写|区间|
|candidates|该帧通过阈值的三尺度候选位置数|位置|
|category|COCOeval张量零基轴索引；分别0.50:0.05:0.95、0:0.01:1、标准80类、all/s/m/l、1/10/100；详见Step1/TENSOR_CSV.md|索引|
|clock|E2限帧sleep调用、参数表达式和时钟API，按列名区分|代码|
|clock_ticks_per_second|内核USER_HZ换算频率，实测100|tick/s|
|column|论文表编号、表内行列索引、段落索引或CSV列序号；row/column从0、ordinal从1开始|索引|
|comm_name|线程comm名称（身份信息已脱敏）|文本|
|condition|CPU策略D/O/L/F600/F1200；历史驻留CSV的policy可能是已脱敏sysfs路径，需按同process_id连接process_summary恢复策略，不能把路径当governor|代号/路径|
|config|实际输出/消费者配置M6、CID_MAX、CID_INDEX、R、F、S、S2等|标识|
|contexts|E6独立SDK上下文槽数|个|
|contrast|有序配置对；时间Δ=X−Y；原归档FPS表若direction指left更快则为FPS左−右，新增FPS表明确right−left|代号|
|cooling_max|采样到的冷却设备最大状态|状态编号|
|core|CPU逻辑核号；last字段为边界瞬时最近运行核，不是完整核调度轨迹|核号|
|cpufreq_policy|相对路径、来源标识或OS根占位符路径（原私人绝对前缀已替换）；按列名和所在CSV区分|路径/标识|
|cpufreq_policy_path|相对路径、来源标识或OS根占位符路径（原私人绝对前缀已替换）；按列名和所在CSV区分|路径/标识|
|detections|NMS后最终检测数|框|
|df|双侧配对Student t置信区间自由度=n_blocks−1|自由度|
|dfl_coord_ms|公共DFL解码及坐标恢复|ms|
|difference_ms|列名前缀指定计时阶段、差值或服务区间的墙钟耗时；同进程正式帧取均值|ms|
|direction|该CSV原有差值符号定义|文本|
|driver|cpufreq驱动名称，实测cpufreq-dt|文本|
|equal|验证范围、检查项、复算值、参照值、绝对差、容许舍入误差或对账布尔项，按列名区分|随所检查指标；equal为0/1|
|errors|读取调度证据失败的异常类型/结构，保留原记录|文本/JSON|
|exact_images_vs_archived_baseline|与历史预测字节完全相同的图像数量|图像|
|excluded|是否包含资源/是否排除该批次/副本是否发生脱敏，按列名区分|0/1|
|filename|相对路径、来源标识或OS根占位符路径（原私人绝对前缀已替换）；按列名和所在CSV区分|路径/标识|
|formal_achieved_FPS|正式帧数/明确记录的墙钟窗口或stream区间；E6 FPS用stream首t0至末t_final，不能用1000/平均latency替代|frame/s|
|formal_actual_samples|正式阶段实际频率读数样本数|次|
|formal_frames|按列名分别为正式记录/帧数、去重帧数或预热帧数|帧/条|
|formal_frequency_max_MHz|频点/按驻留时间加权均频/正式阶段采样最小或最大频率，按列名区分|MHz|
|formal_frequency_min_MHz|频点/按驻留时间加权均频/正式阶段采样最小或最大频率，按列名区分|MHz|
|formal_passes|每进程正式遍数；一般3，E2为30|遍|
|formal_process_CPU_one_core_percent|100×进程(user+sys)CPU秒/同窗口wall秒；100%为一个核；多线程可超过100%；pooled为先加分子分母，process_mean为各进程比值均值|% of one core|
|formal_records|按列名分别为正式记录/帧数、去重帧数或预热帧数|帧/条|
|formal_rows|按列名分别为正式记录/帧数、去重帧数或预热帧数|帧/条|
|formal_sys_seconds|列名前缀指定的进程/线程user、sys或wall时间；formal/per_pass/whole窗口严格分开，sum为先合计，mean为独立进程均值|s|
|formal_user_seconds|列名前缀指定的进程/线程user、sys或wall时间；formal/per_pass/whole窗口严格分开，sum为先合计，mean为独立进程均值|s|
|formal_wall_seconds|列名前缀指定的进程/线程user、sys或wall时间；formal/per_pass/whole窗口严格分开，sum为先合计，mean为独立进程均值|s|
|forward_completions|实际已完成SDK模型前向计数|次|
|frame|视频单遍帧索引，从0开始|帧|
|frames|按列名分别为正式记录/帧数、去重帧数或预热帧数|帧/条|
|frames_file|相对路径、来源标识或OS根占位符路径（原私人绝对前缀已替换）；按列名和所在CSV区分|路径/标识|
|frequency_MHz|频点/按驻留时间加权均频/正式阶段采样最小或最大频率，按列名区分|MHz|
|full_float_bbox_elements|全量恢复浮点bbox元素数/候选读取真实整数元素数/平均恢复元素数，按列名区分|元素|
|governor|实际记录的CPU governor名称|文本|
|identity_source|资源类别、身份核验来源、获取/权利说明或源文件类别，按列名区分|文本|
|images|评价图像总数/预测条数，按列名区分|图像/框|
|included|是否包含资源/是否排除该批次/副本是否发生脱敏，按列名区分|0/1|
|independent_per_core_counter|共享policy映射标志/是否独立逐核硬件计数，按列名区分|0/1或True/False|
|index|原worker/冻结顺序索引，从0开始|索引|
|iou|COCOeval张量零基轴索引；分别0.50:0.05:0.95、0:0.01:1、标准80类、all/s/m/l、1/10/100；详见Step1/TENSOR_CSV.md|索引|
|is_process_main_thread|是否为进程主线程|0/1|
|item|验证范围、检查项、复算值、参照值、绝对差、容许舍入误差或对账布尔项，按列名区分|随所检查指标；equal为0/1|
|kernel|运行内核版本字符串|版本|
|kind|资源类别、身份核验来源、获取/权利说明或源文件类别，按列名区分|文本|
|last_core_after|CPU逻辑核号；last字段为边界瞬时最近运行核，不是完整核调度轨迹|核号|
|last_core_before|CPU逻辑核号；last字段为边界瞬时最近运行核，不是完整核调度轨迹|核号|
|last_cpu|CPU逻辑核号；last字段为边界瞬时最近运行核，不是完整核调度轨迹|核号|
|last_processor|CPU逻辑核号；last字段为边界瞬时最近运行核，不是完整核调度轨迹|核号|
|left|有序比较的左/右配置|代号|
|left_FPS|正式帧数/明确记录的墙钟窗口或stream区间；E6 FPS用stream首t0至末t_final，不能用1000/平均latency替代|frame/s|
|left_ms|列名前缀指定计时阶段、差值或服务区间的墙钟耗时；同进程正式帧取均值|ms|
|matching_threads_at_formal_boundaries|在边界成功匹配线程数/可得迁移累计值线程数，按列名区分|线程|
|maxdet|COCOeval张量零基轴索引；分别0.50:0.05:0.95、0:0.01:1、标准80类、all/s/m/l、1/10/100；详见Step1/TENSOR_CSV.md|索引|
|maximum_kHz|scaling_min_freq/scaling_max_freq边界配置，非负载实际频率|kHz|
|mean|stage指定指标的均值/样本标准差/双侧95%区间下界/上界；SD分母n−1，CI用独立区组而非帧|由stage决定；通常ms|
|mean_FPS_right_minus_left|右配置FPS−左配置FPS；正值表示右侧吞吐更高，区别于时间左−右符号|frame/s|
|mean_difference_ms|列名前缀指定计时阶段、差值或服务区间的墙钟耗时；同进程正式帧取均值|ms|
|mean_paired_block_percent|各独立区组百分比差值的均值/样本SD/双侧95%区间边界；与比值的均值区别保留|%|
|measured_FPS|正式帧数/明确记录的墙钟窗口或stream区间；E6 FPS用stream首t0至末t_final，不能用1000/平均latency替代|frame/s|
|method|分位数计算方法，本包为NumPy linear|文本|
|migration_count|可得的线程迁移累计/差值；空值或NA为未取得，绝不等于0；边界值不证明逐帧无迁移|次/NA|
|migration_scope|迁移信息的可观测范围说明|文本|
|migrations_cumulative|可得的线程迁移累计/差值；空值或NA为未取得，绝不等于0；边界值不证明逐帧无迁移|次/NA|
|migrations_delta|可得的线程迁移累计/差值；空值或NA为未取得，绝不等于0；边界值不证明逐帧无迁移|次/NA|
|minimum_kHz|scaling_min_freq/scaling_max_freq边界配置，非负载实际频率|kHz|
|mode|历史COCO评测配置M6/R/F等|标识|
|monitor_one_core_CPU_percent|监测线程同窗口CPU时间/墙钟时间×100|% of one core|
|monitor_poll_CPU_max_ms|监测单次轮询线程CPU耗时/墙钟耗时的最大值，按列名区分|ms|
|monitor_poll_wall_max_ms|监测单次轮询线程CPU耗时/墙钟耗时的最大值，按列名区分|ms|
|monitor_runtime_thread_CPU_seconds|监测运行期自身线程CPU时间/运行墙钟时间，按列名区分|s|
|monitor_runtime_wall_seconds|监测运行期自身线程CPU时间/运行墙钟时间，按列名区分|s|
|monotonic_ns|旁路/边界采样时单调墙钟时间戳|ns|
|n|独立进程或配对区组数，按stage/contrast上下文区分，非逐帧重复数|个|
|n_blocks|独立进程或配对区组数，按stage/contrast上下文区分，非逐帧重复数|个|
|n_independent_blocks|独立进程或配对区组数，按stage/contrast上下文区分，非逐帧重复数|个|
|n_processes_or_paired_blocks|独立进程或配对区组数，按stage/contrast上下文区分，非逐帧重复数|个|
|negative|配对差值为正/负的区组数（按列名区分）|区组|
|negative_blocks|配对差值为正/负的区组数（按列名区分）|区组|
|new_forwards|本次离线整理新增前向/进程/板端运行数，按列名区分|次|
|new_processes|本次离线整理新增前向/进程/板端运行数，按列名区分|次|
|nms_assemble_ms|公共NMS及最终数组组织|ms|
|output_access_ms|SDK输出buffer映射/NumPy视图访问耗时|ms|
|overlap_percent_stream|100×SDK/CPU服务交集长度/stream长度|%|
|overlap_seconds|SDK包络区间集合与CPU后处理服务区间集合的交集长度累计/配置均值或SD；不是纯BPU硬件重叠|ns或s，按后缀|
|p50_ms|按列名所示阶段的正式逐帧linear分位数；配置级为合并帧描述，不作独立重复|ms|
|p95_ms|按列名所示阶段的正式逐帧linear分位数；配置级为合并帧描述，不作独立重复|ms|
|p99_ms|按列名所示阶段的正式逐帧linear分位数；配置级为合并帧描述，不作独立重复|ms|
|pacing|free、fps30、fps15限帧模式|代号|
|pacing_wait_ns|E2 release时刻−sleep前时刻，含调度等待|ns|
|package_bytes|原件/包内文件长度，按列名区分|byte|
|package_directory|相对路径、来源标识或OS根占位符路径（原私人绝对前缀已替换）；按列名和所在CSV区分|路径/标识|
|package_path|相对路径、来源标识或OS根占位符路径（原私人绝对前缀已替换）；按列名和所在CSV区分|路径/标识|
|package_sha256|原件/副本/预测完整SHA-256身份，按列名区分|64位十六进制|
|paired_percent_CI95_high|各独立区组百分比差值的均值/样本SD/双侧95%区间边界；与比值的均值区别保留|%|
|paired_percent_CI95_low|各独立区组百分比差值的均值/样本SD/双侧95%区间边界；与比值的均值区别保留|%|
|paired_percent_sample_SD|各独立区组百分比差值的均值/样本SD/双侧95%区间边界；与比值的均值区别保留|%|
|paragraph|论文表编号、表内行列索引、段落索引或CSV列序号；row/column从0、ordinal从1开始|索引|
|parameter|governor可调参数名；sampling_rate/rate_limit_us为微秒，up_threshold为百分比，其余见对应参数|参数名|
|parameter_path|相对路径、来源标识或OS根占位符路径（原私人绝对前缀已替换）；按列名和所在CSV区分|路径/标识|
|pass|正式遍号，从1开始；phase=formal整段驻留行中0表示聚合窗口|遍|
|pass_sys_seconds|列名前缀指定的进程/线程user、sys或wall时间；formal/per_pass/whole窗口严格分开，sum为先合计，mean为独立进程均值|s|
|pass_user_seconds|列名前缀指定的进程/线程user、sys或wall时间；formal/per_pass/whole窗口严格分开，sum为先合计，mean为独立进程均值|s|
|pass_wall_seconds|列名前缀指定的进程/线程user、sys或wall时间；formal/per_pass/whole窗口严格分开，sum为先合计，mean为独立进程均值|s|
|path|相对路径、来源标识或OS根占位符路径（原私人绝对前缀已替换）；按列名和所在CSV区分|路径/标识|
|percent|列名前缀所定义的百分比，具体分子分母见本行stage/contrast与DATA_DICTIONARY总则|%|
|period_fps15_ns|E2按int(1e9/fps)截取的目标帧周期|ns|
|period_fps30_ns|E2按int(1e9/fps)截取的目标帧周期|ns|
|phase|测量时间窗口/阶段：formal、per_pass、whole_reaped_process等；不可混用分子分母|代号|
|pid|内核进程ID，非账号|PID|
|policy|CPU策略D/O/L/F600/F1200；历史驻留CSV的policy可能是已脱敏sysfs路径，需按同process_id连接process_summary恢复策略，不能把路径当governor|代号/路径|
|position|区组内执行位置，从1开始|位置|
|positive|配对差值为正/负的区组数（按列名区分）|区组|
|positive_blocks|配对差值为正/负的区组数（按列名区分）|区组|
|post_ms|从输出访问开始至完整检测结果可用的CPU后处理服务时间；E6不含排队等待|ms|
|post_start_ns|E6 CPU后处理服务实际开始时刻；串行归档对应forward返回边界|ns|
|pre_ms|读取NV12帧与长度校验的墙钟耗时|ms|
|prediction_max_det|每图预先保留预测数上限，与COCOeval的maxDets设置区别保留|框/图|
|prediction_sha256|原件/副本/预测完整SHA-256身份，按列名区分|64位十六进制|
|predictions|评价图像总数/预测条数，按列名区分|图像/框|
|process|进程编号或原进程目录标识，按所在CSV保留原表示|标识|
|process_file|相对路径、来源标识或OS根占位符路径（原私人绝对前缀已替换）；按列名和所在CSV区分|路径/标识|
|process_id|内核进程ID，非账号|PID|
|process_index|批次内进程序号，从1开始|序号|
|process_sys_seconds|列名前缀指定的进程/线程user、sys或wall时间；formal/per_pass/whole窗口严格分开，sum为先合计，mean为独立进程均值|s|
|process_user_seconds|列名前缀指定的进程/线程user、sys或wall时间；formal/per_pass/whole窗口严格分开，sum为先合计，mean为独立进程均值|s|
|process_wall_seconds|列名前缀指定的进程/线程user、sys或wall时间；formal/per_pass/whole窗口严格分开，sum为先合计，mean为独立进程均值|s|
|processes|独立进程或配对区组数，按stage/contrast上下文区分，非逐帧重复数|个|
|queue_wait_ms|E6 forward完成至CPU后处理服务开始的队列等待|ms|
|ratio_of_means_percent_point_estimate|100×(左配置进程均值−右配置进程均值)/左配置进程均值；比值的点估计|%|
|raw_USER_HZ_delta|time_in_state原累计计数之差，USER_HZ=100|tick(0.01s)|
|raw_block_differences|按原冻结区组编号排列的全部配对差值数组|由stage决定；ms或FPS|
|raw_block_values|该行FPS均值、样本SD、双侧Student t区间端点或原始区组差值，按列名区分|frame/s|
|raw_tick_delta|<PROC_ROOT>/stat或task stat的user/system/total/busy计数或完整差值向量，按列名区分|USER_HZ tick|
|recall|COCOeval张量零基轴索引；分别0.50:0.05:0.95、0:0.01:1、标准80类、all/s/m/l、1/10/100；详见Step1/TENSOR_CSV.md|索引|
|recomputed|验证范围、检查项、复算值、参照值、绝对差、容许舍入误差或对账布尔项，按列名区分|随所检查指标；equal为0/1|
|recovered_elements_mean|全量恢复浮点bbox元素数/候选读取真实整数元素数/平均恢复元素数，按列名区分|元素|
|redacted|是否包含资源/是否排除该批次/副本是否发生脱敏，按列名区分|0/1|
|reference|验证范围、检查项、复算值、参照值、绝对差、容许舍入误差或对账布尔项，按列名区分|随所检查指标；equal为0/1|
|related_cpus|允许CPU亲和性列表或cpufreq共享策略覆盖核列表，按列名区分|核号列表|
|relative_reduction_percent_ratio_of_means|100×(左配置进程均值−右配置进程均值)/左配置进程均值；比值的点估计|%|
|release_target_ns|E2该帧预定release时刻|ns|
|requested_table|请求表编号、对应Rev13表号、来源批次或版本/范围匹配状态，按列名区分|编号/标识|
|residency_seconds|正式或逐遍窗口频率驻留秒数（或其进程汇总）；phase=formal与per_pass是重叠口径，不可相加|s|
|resident_wall_seconds|正式或逐遍窗口频率驻留秒数（或其进程汇总）；phase=formal与per_pass是重叠口径，不可相加|s|
|restore_ms|恢复/候选组织：R浮点候选提取、F全量恢复+候选提取、S/S2候选整数取数+恢复+组织|ms|
|right|有序比较的左/右配置|代号|
|right_FPS|正式帧数/明确记录的墙钟窗口或stream区间；E6 FPS用stream首t0至末t_final，不能用1000/平均latency替代|frame/s|
|right_ms|列名前缀指定计时阶段、差值或服务区间的墙钟耗时；同进程正式帧取均值|ms|
|role|线程角色inference/postprocessing等|代号|
|row|论文表编号、表内行列索引、段落索引或CSV列序号；row/column从0、ordinal从1开始|索引|
|rows_per_process_in_bin|该独立进程落入候选区间的正式记录数|帧|
|sample_SD|该行FPS均值、样本SD、双侧Student t区间端点或原始区组差值，按列名区分|frame/s|
|sched_error|读取调度证据失败的异常类型/结构，保留原记录|文本/JSON|
|scope|验证范围、检查项、复算值、参照值、绝对差、容许舍入误差或对账布尔项，按列名区分|随所检查指标；equal为0/1|
|sdk_ms|输入复制/cache clean/提交等待/输出invalidate及任务释放的外部SDK调用包络，非纯BPU时间|ms|
|select_ms|分类响应处理、阈值筛选和候选索引生成；包含各配置必要分类消费差异|ms|
|selected_integer_bbox_elements|全量恢复浮点bbox元素数/候选读取真实整数元素数/平均恢复元素数，按列名区分|元素|
|sha256|原件/副本/预测完整SHA-256身份，按列名区分|64位十六进制|
|shared_policy|共享cpufreq policy标识，实际为policy0|标识|
|shared_policy_mapping|共享policy映射标志/是否独立逐核硬件计数，按列名区分|0/1或True/False|
|sign|派生FPS差值符号说明|文本|
|sleep_argument|E2限帧sleep调用、参数表达式和时钟API，按列名区分|代码|
|sleep_function|E2限帧sleep调用、参数表达式和时钟API，按列名区分|代码|
|sleep_inside_frame_step|E2布尔定义项，按列名区分|0/1|
|slot|E6 SDK buffer槽索引|0/1|
|source|请求表编号、对应Rev13表号、来源批次或版本/范围匹配状态，按列名区分|编号/标识|
|source_bytes|原件/包内文件长度，按列名区分|byte|
|source_id|相对路径、来源标识或OS根占位符路径（原私人绝对前缀已替换）；按列名和所在CSV区分|路径/标识|
|source_sha256|原件/副本/预测完整SHA-256身份，按列名区分|64位十六进制|
|stage|本行所统计的计时阶段，含单位后缀|代号|
|start_lateness_ns|E2 max(0,实际release−target)|ns|
|status|请求表编号、对应Rev13表号、来源批次或版本/范围匹配状态，按列名区分|编号/标识|
|strategy|实际输出/消费者配置M6、CID_MAX、CID_INDEX、R、F、S、S2等|标识|
|stream_ns|E6正式stream末t_final−首t0或其配置均值/SD|ns或s，按后缀|
|stream_seconds|E6正式stream末t_final−首t0或其配置均值/SD|ns或s，按后缀|
|stream_seconds_mean|E6正式stream末t_final−首t0或其配置均值/SD|ns或s，按后缀|
|stream_seconds_sample_SD|E6正式stream末t_final−首t0或其配置均值/SD|ns或s，按后缀|
|sum_observed_migration_delta|可得的线程迁移累计/差值；空值或NA为未取得，绝不等于0；边界值不证明逐帧无迁移|次/NA|
|summed_resident_wall_seconds|正式或逐遍窗口频率驻留秒数（或其进程汇总）；phase=formal与per_pass是重叠口径，不可相加|s|
|sys_seconds|列名前缀指定的进程/线程user、sys或wall时间；formal/per_pass/whole窗口严格分开，sum为先合计，mean为独立进程均值|s|
|sys_seconds_boundary_delta|列名前缀指定的进程/线程user、sys或wall时间；formal/per_pass/whole窗口严格分开，sum为先合计，mean为独立进程均值|s|
|sys_seconds_sum|列名前缀指定的进程/线程user、sys或wall时间；formal/per_pass/whole窗口严格分开，sum为先合计，mean为独立进程均值|s|
|sys_ticks|<PROC_ROOT>/stat或task stat的user/system/total/busy计数或完整差值向量，按列名区分|USER_HZ tick|
|t0_after_sleep|E2布尔定义项，按列名区分|0/1|
|t0_ns|输入读取前的单调墙钟时间；E2在sleep之后|ns|
|t_final_ns|最终检测数组可用时刻|ns|
|t_forward_ns|forward同步调用返回时刻|ns|
|t_outputs_ns|输出buffer视图访问完成时刻|ns|
|t_post_start_ns|E6 CPU后处理服务实际开始时刻；串行归档对应forward返回边界|ns|
|t_prepare_ns|输入prepare调用完成时刻|ns|
|t_read_ns|NV12读取和长度校验结束时刻|ns|
|table|论文表编号、表内行列索引、段落索引或CSV列序号；row/column从0、ordinal从1开始|索引|
|temperature_max_C|旁路正式阶段可得温度采样最小/最大值|°C|
|temperature_min_C|旁路正式阶段可得温度采样最小/最大值|°C|
|text|原论文只读科学文本/表单元格，不包括作者信息|文本|
|threads_with_observed_cumulative_migration_delta|在边界成功匹配线程数/可得迁移累计值线程数，按列名区分|线程|
|tid|内核线程ID|TID|
|time_weighted_mean_MHz|频点/按驻留时间加权均频/正式阶段采样最小或最大频率，按列名区分|MHz|
|tolerance|验证范围、检查项、复算值、参照值、绝对差、容许舍入误差或对账布尔项，按列名区分|随所检查指标；equal为0/1|
|total_ms|t_final−t0；串行为完整端到端，E6含QueueWait，E2不含此前sleep|ms|
|total_ticks|<PROC_ROOT>/stat或task stat的user/system/total/busy计数或完整差值向量，按列名区分|USER_HZ tick|
|tunables|完整governor参数字典|JSON|
|tunables_scope|该行tunables来自冻结governor_reference；min/max/governor来自真实边界读数，不将参考参数冒充逐次重新读取|文本|
|unique_frames|按列名分别为正式记录/帧数、去重帧数或预热帧数|帧/条|
|user_seconds|列名前缀指定的进程/线程user、sys或wall时间；formal/per_pass/whole窗口严格分开，sum为先合计，mean为独立进程均值|s|
|user_seconds_boundary_delta|列名前缀指定的进程/线程user、sys或wall时间；formal/per_pass/whole窗口严格分开，sum为先合计，mean为独立进程均值|s|
|user_seconds_sum|列名前缀指定的进程/线程user、sys或wall时间；formal/per_pass/whole窗口严格分开，sum为先合计，mean为独立进程均值|s|
|user_ticks|<PROC_ROOT>/stat或task stat的user/system/total/busy计数或完整差值向量，按列名区分|USER_HZ tick|
|utilization_percent|原<PROC_ROOT>/stat系统或单核busy_ticks/total_ticks×100，不是进程CPU%|%|
|value|COCO张量值(0–1或-1缺失)，或governor参数原始值（单位由parameter确定），按所在CSV区分|0–1/-1或参数单位|
|video|视频A/B/C|标识|
|wall_seconds|列名前缀指定的进程/线程user、sys或wall时间；formal/per_pass/whole窗口严格分开，sum为先合计，mean为独立进程均值|s|
|wall_seconds_sum|列名前缀指定的进程/线程user、sys或wall时间；formal/per_pass/whole窗口严格分开，sum为先合计，mean为独立进程均值|s|
|warmup_frames|按列名分别为正式记录/帧数、去重帧数或预热帧数|帧/条|
|window|测量时间窗口/阶段：formal、per_pass、whole_reaped_process等；不可混用分子分母|代号|
|worker_boundary_sampling_CPU_ms|worker边界采样累计线程CPU/墙钟耗时，按列名区分|ms|
|worker_boundary_sampling_count|worker边界采样次数|次|
|worker_boundary_sampling_wall_ms|worker边界采样累计线程CPU/墙钟耗时，按列名区分|ms|
