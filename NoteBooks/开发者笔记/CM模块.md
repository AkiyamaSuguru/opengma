# CM模块开发者笔记
CM模块是GMA中最主要的模块，所有的表征方法处理都会集成到这个模块中，目前正在开发的表征方法处理子模块包括
XRD，Raman，XPS等。

大部分表征方法的代码块包含 读取，分析，绘图模块，分别标记
为[X]Loder,[X]Analyzer,[X]Plotter。其中在具体表征
方法等子模块下，分别设有loder，analyzer，plotter入口，
具体的代码模块则放入[X]Loder,[X]Analyzer,[X]Plotter
命名的字文件夹下面。