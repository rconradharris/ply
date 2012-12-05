import setuptools


setuptools.setup(
    name='ply_patch',
    version='0.1',
    description='Ply: Git-based Patch Management',
    url='https://github.com/rconradharris/ply',
    license='MIT',
    author='Rick Harris',
    author_email='rconradharris@gmail.com',
    packages=setuptools.find_packages(),
    classifiers=[
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2.6'
    ],
    install_requires=[],
    scripts=['bin/ply']
)
