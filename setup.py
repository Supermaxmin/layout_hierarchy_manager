from setuptools import setup, find_packages

setup(
    name = "layoutHier",
    version = '0.1',
    description = "This package includes classes to extract layout hierarchy.",
    author = "Meenchow Yin",
    author_email = "yinmch17@mails.tsinghua.edu.cn",
    packages = find_packages(),
    include_package_data = True,	# only work for bdist command
	# exclude_package_data = {
			# 'layoutHier': ['*readme.txt']},
    dependencies = [
    'klayout >= 0.26.0',
    'Rtree >= 0.8.3',
    'bintrees >= 2.0.7'
    ],
    classifiers = [
    'Topic :: Software Development :: Electronic Design Automation',
    'Programming Language :: Python :: 3.7',
    ]

)
