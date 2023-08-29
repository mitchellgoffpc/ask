#!/usr/bin/env python3

import os
from setuptools import setup

directory = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(directory, 'README.md'), encoding='utf-8') as f:
  long_description = f.read()

setup(name='ask',
      version='0.1.0',
      description='ask questions to a chatbot',
      author='Mitchell Goff',
      license='MIT',
      long_description=long_description,
      long_description_content_type='text/markdown',
      packages = ['ask'],
      classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License"
      ],
      install_requires=['requests', 'tqdm'],
      python_requires='>=3.8',
      extras_require={
        'linting': [
          "flake8",
          "pylint",
          "mypy",
          "pre-commit",
        ],
      },
      entry_points={
        'console_scripts': [
          'ask=ask.main:main'
        ]
      },
      include_package_data=True)
