"""
Mongogut
-------------

GUT interface to Mongo
"""
from setuptools import setup

setup(
    name='mongogut',
    version='0.1',
    url='https://github.com/rahuldave/mongogut',
    license='MIT',
    author='Rahul Dave',
    author_email='rahuldave@gmail.com',
    description='A mongo version of GUT',
    long_description=__doc__,
    package_dir = {'': '.'},
    packages=['.'],
    py_modules=['mongogut'],
    install_requires=[
        'pymongo',
        'simplejson'
    ],
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Software Development :: Libraries'
        ],
)