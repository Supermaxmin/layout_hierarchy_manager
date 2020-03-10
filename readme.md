# LayoutHier Package Usage

---
   layoutHier package integrates two arrays managers and an hierarchy manager, namely, **ProjectArrayManager** , **SplitArrayManager** which are named after their implementation details, and **HierarchyManager**. With array patterns detected and feeded by arrays managers, hierarchy manager extract layout hierarchy from unit patterns. Finally, hierarchy within pattern tree is mapped back into original layout.

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

###ArrayManager test results
Hierarchies of **testcase1.gds**, **testcase2.gds** are restored and the corresponding file is located in *./layout/out/arrays*.  ![root_instance](https://github.com/Supermaxmin/layout_hierarchy_manager/tree/master/test_results/root_instance.png)

<font color=red>NOTE: Remember to replace the testcase with yours.</font>




