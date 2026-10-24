# PULSE 项目论文参考材料

这里保存 PULSE 项目既有论文工程的 LaTeX 副本，供项目研究报告撰写不确定性来源分类、需求端量化与主动感知方法时查阅。它是参考快照，不是两份项目研究报告的主稿，也不是与原论文仓库自动同步的工作目录。

论文暂题为 *Towards Pre-generation Requirement Uncertainty Assessment for Code Generation*。`main.tex` 是入口；`Sections/`、`tables/`、`figures/` 和 `Reference.bib` 分别保存章节、表格、图件和参考文献。项目研究报告主稿及转换方法见[协作仓库 README](../../README.md)。

使用时可参考论文对需求扰动、需求条件化不确定性、生成前识别和选择性澄清的定义与写法。论文中的六种文本扰动属于实验构造操作，不直接等同于项目级不确定性来源分类；论文实验数字、模型配置和结论也应与当前研究备份的原始记录核对后再写入项目报告。引用该目录时注明所依据的文件和版本，不将复制时间当作实验完成时间。

如需本地编译，在此目录安装 LaTeX 工具链后运行 `./build.ps1`；输出位于被 `.gitignore` 排除的 `build/`。此处不配置论文原仓库或 Overleaf 的同步远程。
