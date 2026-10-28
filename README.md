# opengma [! 本项目正在开发中]
Open general material analyzer. OPEN GMA 为 Jay 开发的材料分析工具集。目前该库还在开发中。我们构思的一个通用材料分析库主要包括下面的功能：

- 数据读取：具有多种数据结构读取借口，数据在分析之前均需要转化为标准数据结构，所以我们会定义标准数据结构来完成数据与后续处理的解耦。
- 数据分析：提供常用的表征方法数据分析模块，进行数据的快速分析。
- 绘图模块：进行学术图形以及交互图形的快速绘制。
- 计算：提供通用以及专用的计算模块，用于常规物理量的计算。
- 结构化存储：采用数据库以及其他数据存储形式，对数据进行结构化存储，方便进行数据复用。

## 设计哲学
为了提高代码的可用性，我们更希望该项目可以像Python库一样使用，通过将整个科研流程中表征数据等分析划分为不同的流程，以此
将代码整理为几个不同的板块，不同板块之间进行解耦方便代码的使用。比如，你有一个本项目中没有提供数据读取方式的数据，但是
你需要使用其他部分或者板块中的代码，那么你可以自行写一个标准的数据读取模块，将数据以本项目规定的数据结构传入进行处理。
这种设计尽可能的增加了代码的可重复使用性，也是本项目最重要的设计哲学所在。

我们使用表征方法来组织项目，这是因为每种表征方法的处理通常是具有共性的，比如数据最终使用的结构是相同的或者类似的，这就
使得对数据输入进行标准化存在可行性。本项目中的表征方式主要是项目作者使用过的一些表征手段，但是我们也期待有新的开发者加入
完善本项目。该项目因为还未开发完成，所以整体以开源传染性开源协议发布，后续我们可能会考虑以MIT等协议发布，取消这种强制
开源传递性方便使用。

## 开发进度
目前XPS部分的绘图以及数据读取已经可以使用，我进行了测试，目前
功能正常。另外Raman和XPS的数据读取模块已经开发完毕。

## License

**Only the code is open source.** Everything else (the author's name and personal information, the design and the content) is reserved.

- **Code: [GNU AGPL-3.0](LICENSE) (`AGPL-3.0-only`), a strong copyleft license.** The Python package in `src/`, `main.py`, the notebooks in `NoteBooks/` and the project files. You may use, study, change and share it. If you share a changed version, or run one as a network service (a web app or an online analysis tool, for example), you must offer its full source code under the same license to everyone who receives it or uses it over the network, keep the copyright and license notices, and mark your changes. It comes with no warranty.
- **Reserved: the author's name and personal information.** Jay Ma (AkiyamaSuguru) and any details about the author.
- **Reserved: design.** The author's emblem in every form, all icons, and every logo, ornament, illustration and other design element, in whatever form and wherever it appears, including any added to this repository later.
- **Reserved: content.** The text of this README and any other content that is not code, such as documents, images and data.

© 2026 Jay Ma. Everything the AGPL does not cover is reserved: **no use in any form** without written permission, commercial or not, including text and data mining and AI training. Fair use that the law allows (personal study, research, or a brief quotation that names its source) needs no permission; please keep within it. Keeping the copyright and license notices in the code, as the AGPL requires, needs none either.

If you build on the code, replace everything reserved with your own. To ask for permission, write to the author at the address on the letter page of the author's homepage (https://akiyamasuguru.github.io/#letter), or through GitHub ([@AkiyamaSuguru](https://github.com/AkiyamaSuguru)).

### 许可说明

**本项目只开源代码**。除代码以外的一切（作者的姓名与个人信息、设计与内容）均保留所有权利。

- **代码：[GNU AGPL-3.0](LICENSE)（`AGPL-3.0-only`），强 Copyleft 许可证**。包括 `src/` 中的 Python 包、`main.py`、`NoteBooks/` 中的笔记本以及项目文件。可以使用、研究、修改与分享；分享修改后的版本，或将其作为网络服务（例如网页应用或在线分析工具）运行时，必须以同一许可证向获得它或通过网络使用它的所有人提供全部源代码，保留版权与许可声明，并注明所作的修改。本软件不提供任何担保。
- **保留**：作者的姓名与个人信息；作者徽标的一切形式、所有图标及其他一切设计元素（包括今后加入本仓库的）；本说明的文字以及其他非代码内容，如文档、图片与数据。

© 2026 Jay Ma。AGPL 不涵盖的一切均保留所有权利：未经书面许可，**禁止以任何形式使用**，无论商业或非商业用途，包括文本与数据挖掘及 AI 训练。法律允许的合理使用（个人学习、研究，或注明出处的适当引用）无需许可，请遵守这一界限；按 AGPL 的要求保留代码中的版权与许可声明，同样无需许可。如需许可，请通过[主页书信页](https://akiyamasuguru.github.io/?lang=zh#letter)上的地址或 GitHub（[@AkiyamaSuguru](https://github.com/AkiyamaSuguru)）联系作者。
