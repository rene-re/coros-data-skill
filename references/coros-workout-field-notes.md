# COROS Workout Field Notes

持续记录 COROS workout / schedule 相关字段的实际含义。只记录已经从账号实测、现有模板、或接口行为中得到的结论；不把猜测写成事实。

## Core identifiers

- `sportType`
  - `1` = 跑步训练
  - `4` = 力量训练
- `exerciseType`
  - `0` = 分组/容器（group header）
  - `1` = 热身类 step
  - `2` = 主训练 step
  - `3` = 放松结束类 step
  - `4` = 恢复/慢跑类 step（常见于组内恢复）

## Target fields

- `targetType`
  - `2` = 按时间目标
    - 例：`targetValue=60` 表示 60 秒
    - 见现有模板：`法特莱克跑`、`恢复跑`、旧版 `LSD`
  - `5` = 按距离目标
    - 例：`targetValue=80000` 对应 800m
    - 推测距离单位是 1/100 米，即 `100000 = 1km`
    - 见现有模板：`亚索800`
  - `1` = 曾被错误映射为距离，但在手表/UI 表现不符合预期；当前不要再用作距离型
- `targetDisplayUnit`
  - `0` = 时间类默认显示
  - `1` = 距离类显示（在 `targetType=5` 的模板中出现）

## Intensity fields

- `intensityType`
  - `0` = 无强度限制 / 默认
  - `2` = 某种有氧/心率相关限制（在现有 `恢复跑`、错误修正后的距离课中出现；具体是心率区还是别的有氧控制，还需继续验证）
  - `3` = 阈值相关强度模板
    - 已确认可能被 UI 显示成阈值配速/阈值相关限制
    - 不应在需要“乳酸阈心率”时直接复用，除非确认字段映射正确
  - `7` = 在现有 `LSD` 模板的短结尾 step 中出现，具体语义待确认
- `intensityDisplayUnit`
  - `0` = 非配速显示或默认显示
  - `1` = 常与 `intensityType=3` 一起出现，疑似配速/阈值类显示
- `isIntensityPercent`
  - `true` 时通常伴随 `intensityPercent` / `intensityPercentExtend`
  - 常出现在阈值相关模板中
- `intensityPercent` / `intensityPercentExtend`
  - 在阈值相关模板中出现
  - 例：`81000 ~ 91000`、`69000 ~ 80000`
  - 疑似相对于某参考阈值或区间的百分比 * 1000
  - 具体到底是阈值配速、阈值心率还是其他强度标尺，仍需继续对照 UI 验证
- `intensityValue` / `intensityValueExtend`
  - 阈值相关模板中常见
  - 例：`378000 ~ 425000`、`426000 ~ 500000`
  - 具体单位未最终确认，不应脱离模板语义单独解释
- `intensityCustom`
  - `0` = 默认
  - `1` / `2` / `3` = 不同强度模板变体；当前仅知道会影响 UI 解释方式，详细意义待确认

## Common text keys

- `name`
  - `T1120` = 热身
  - `T1122` = 放松结束
  - `T1123` = 恢复/慢跑恢复段
  - `T3001` = 主训练段
- `overview`
  - `sid_run_warm_up_dist` = 跑步热身描述
  - `sid_run_cool_down_dist` = 跑步放松/恢复描述
  - `sid_run_training` = 跑步主训练描述

## Schedule/update fields

- `idInPlan`
  - 日程中的计划内编号
  - 创建 schedule 时通常取 `maxIdInPlan + 1`
- `sortNoInSchedule`
  - 当天排序，`1` 表示当天第一节
- `versionObjects[].status`
  - `1` = 新增/生效
  - `3` = 删除
- `pbVersion`
  - schedule update 目前实测用 `2` 可成功

## Known pitfalls

- 不能把 `targetType=1` 当成距离型稳定使用；UI 可能显示成自由模式或异常模式。
- 不能直接复用阈值模板就假定它是“乳酸阈心率”；同样的阈值字段组合可能被 UI 解释成阈值配速。
- 造 workout 时，外层 `name` 改了不代表内部描述就改对了；`overview` / `intensityType` / `targetType` 必须一起对齐。

## Open questions

- 哪组字段组合会被 COROS UI 明确识别为“乳酸阈心率”？
- `intensityType=2` 的精确含义是什么？
- `intensityType=3` 是否稳定等价于阈值配速模板？
- 距离型 + 心率型限制的正确最小字段集是什么？
