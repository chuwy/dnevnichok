#!/usr/bin/env python

from setuptools import setup


setup(name='dnevnichok',
      version='0.0.1',
      description=open('README.rst', 'r').read(),
      author='Anton Parkhomenko',
      author_email='mailbox@chuwy.me',
      url='http://chuwy.ru/dnevnichok',
      install_requires=['docutils'],
      packages=['dnevnichok'],
      scripts = ['bin/dnev'],
      license='MIT'
      )
