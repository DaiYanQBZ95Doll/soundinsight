# SoundInsight 边界案例清单

本文档整理模型在真实数据上容易出错的边界场景，用于后续精标与评测设计。每个类别给出定义、判断标准与真实样例（样例取自十万条 Amazon Electronics 评论）。

## 一、委婉表达类

定义：评论在批评音质，但用词缓和，不含负面关键词，如 disappointed、could be better、not as expected。

判断标准：出现降级期望、对比失望或条件句，需结合整体语义判断。

真实样例：

1. Was expecting a deeper bass given the price point, but it is acceptable for casual listening.
2. The sound is fine for the price, nothing special.

处理建议：这类样本是规则初筛与二分类模型的主要漏检来源，建议纳入人工精标集，配合 LLM 复核二次兜底。

## 二、中性比较类

定义：评论以对比为主，同时提到优劣两面，难以二分，如自家产品与旧款或其他品牌比较。

判断标准：存在对比对象且整体语气中性，无明确差评结论时判为正常，不强行归为负面。

真实样例：

1. Not as loud as my previous pair, but the clarity is actually better.
2. Bass is weaker than brand X, treble is smoother though.

处理建议：在标注规范中明确中性比较归为正常，避免模型学到伪特征；评测时单独统计该类别的误报率。

## 三、含关键词但非音质差评类

定义：评论命中音质关键词，但语义与音质缺陷无关，如动词用法 sound like、产品包装提到 crisp、物流提到 static 等。

判断标准：关键词须指向耳机音质属性本身，动词性用法与比喻用法不计入。

真实样例：

1. It sounds like a great deal, and shipping was fast.
2. The packaging keeps the unit safe from static damage.

处理建议：这类是弱标注阶段的主要误报来源，LLM 复核已过滤大部分，人工精标时应抽查规则正例中的残留。

## 四、评分与语义冲突类

定义：评分与文字不一致，如五星但文字批评音质，或两星但问题在物流而非音质。

判断标准：以音质相关文字语义为准，评分仅作初筛参考。

真实样例：

1. 五星：Great product, though the bass is a little muddy.
2. 两星：Arrived broken due to poor packaging, refund was quick.

处理建议：评测报告按文字语义标注，评分冲突样本单列统计，用于向评委说明阈值设计的合理性。

## 五、多语言与混合语言类

定义：非英文或中英混杂评论，当前模型未覆盖。

判断标准：非英文评论暂不参与判定，标记为待扩展。

真实样例：

1. La calidad del sonido es regular, esperaba más graves.
2. 音质一般般，低音不够，有点失望。

处理建议：列为未来工作，接入多语言基座模型后统一处理。

## 六、极短评论类

定义：评论过短导致上下文不足，如只有 broken、meh、terrible。

判断标准：短文本以关键词判定为主，无法判断时归为正常并标记低置信。

真实样例：

1. Meh.
2. Sound broke after a week.

处理建议：统计短文本占比与低置信区间，Demo 展示时对低置信样本给出提示语。
