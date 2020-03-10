# LayoutHier Package Usage

---
LayoutHier package integrates two arrays managers and an hierarchy manager, namely, **ProjectArrayManager** , **SplitArrayManager** which are named after their implementation details, and **HierarchyManager**. With array patterns detected and feeded by arrays managers, hierarchy manager extract layout hierarchy from unit patterns. Finally, hierarchy within pattern tree is mapped back into original layout.

## installation and test
- To intall the package, please git clone the repository and decompress, then open directory ***layout_hierarchy_manager***. Use the script bellow,
`python setup.py install`
- The test cases are placed in **test.py**, after *install* you can test the algorithm through script bellow,

```
python -m unittest test.py  # test all cases
python -m unittest test.ArrayManagerTest    # test one feature
python -m unittest test.ArrayManagerTest.testSArrayManager  # test one method 
```

## test result

### ArrayManager test results
Hierarchies of **testcase1.gds**, **testcase2.gds** are restored and the corresponding file is located in *"./layout/out/arrays"*.  

<p align='center'> <img width='500' src='https://github.com/Supermaxmin/layout_hierarchy_manager/blob/master/test_results/root_instance.png'></p>
<p align='center'> Root instance of **testcase1.gds**</p>

<p align='center'> <img width='500' src='https://github.com/Supermaxmin/layout_hierarchy_manager/blob/master/test_results/arrays_project.png'></p>
<p align='center'> Arrays detected by **ProjectArrayManager** </p>

<p align='center'> <img width='500' src='https://github.com/Supermaxmin/layout_hierarchy_manager/blob/master/test_results/array_cell_project.png'></p>
<p align='center'> Array cell detail </p>

<p align='center'> <img width='500' src='https://github.com/Supermaxmin/layout_hierarchy_manager/blob/master/test_results/arrays_split.png'></p>
<p align='center'> Arrays detected by **SplitArrayManager**</p>

<p align='center'> <img width='500' src='https://github.com/Supermaxmin/layout_hierarchy_manager/blob/master/test_results/array_cell_split.png'></p>
<p align='center'> Array cell detail</p>





