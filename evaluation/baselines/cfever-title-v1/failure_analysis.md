# 冻结基准的检索失败样本

Only page-title lexical retrieval on this frozen subset. No classification, full-text RAG, semantic embedding or LLM accuracy claim.

测试集指标保存在 summary.json；不能写成本项目端到端RAG效果。以下为全部test Top-10未命中的样本，未自动虚构失败原因。

## CFEVER-DEV-27342
主张：第38任美國總統雷根，曾經從事體育運動播報的工作。
官方证据页：羅納德·里根
实际Top-10：美國, 中華民國總統, 共和黨_(美國), 2019年歐洲運動會
待分析：别名/字形差异、主张未显式提及证据标题、词项歧义；需人工逐条确认。

可直接复核的词项诊断：证据页「羅納德·里根」完整标题包含=False，共享bigram=[]。
