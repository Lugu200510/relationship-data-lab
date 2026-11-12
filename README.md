# 网恋研究所

[打开网站](https://lugu200510.github.io/relationship-data-lab/)

这个静态网站汇总 Stanford HCMST 2017 基线及 2020、2022 年随访。默认展示从恋爱关系开始到 24 个月内报告结婚的比例，61 / 319 = 19.1%。切换期限可以查看 12 和 36 个月的结果。

直接打开 index.html 即可离线测试。页面只包含汇总计数。

## 复算

从 [Stanford Libraries](https://data.stanford.edu/hcmst2017) 获取 Stata v2.2 数据并查看使用说明。安装 pandas 后运行：

    python reproduce_hcmst.py "path/to/hcmst.dta" --output hcmst-summary.js

输出包含网页内嵌的 HCMST 汇总。样本筛选、日期规则和来源见脚本与页面的统计口径。

