from setuptools import setup, find_packages

setup (
    # name in the pypi, easy_install or egg name
    name="Transmitor",
    version="1.0",
    keywords=["transmitor", "bridge", "network", "intranet"],
    description="network transmitor",
    long_description="make your local intranet service can be directly accessed from the internet, just like teamview, but more powerful.",
    license="GPLv3",
    url="http://www.springvi.com/transmitor",
    author="SpringVi",
    author_email="springvi@qq.com",

    # dir list to be packaged
    packages=find_packages(),
    # packages=[
    #     "com",
    #     "com.cleverworld.spring",
    #     "com.cleverworld.spring.transmitor",
    #     "com.cleverworld.spring.transmitor.conf"
    # ],

    include_package_data=True,
    package_data = {'': ['*.yaml']},
    platforms="3.7",

    # depend on libraries
    install_requires=[
        "PyYAML>=3.13"
    ],
    scripts=[],

    # entry point definition
    entry_points={
        "console_scripts":[
            "Transmitor=com.cleverworld.spring.Transmitor:main"
        ]
    },
    # py_modules=["Transmitor.py", "Utils.py", "BusinessListener.ph", "ConnectSyncChannel.py", "BusinessConnector.py", "CommandChannel.py"],

    classifiers=[
        "Development Status :: 1 - Alpha",
        "Topic :: Utilities",
        "License :: OSI Approved :: GNU General Public License (GPL)"
    ],

    zip_safe=False

)

'''
usage:
1, build
python setup.py build
2, install
python setup.py install
3, run test in windows
Transmitor
4，run in linux server
nohup Transmitor > tmp 2>&1 &

1、generate gzip package
    setup.py sdist
    
2、generate binary windows installer or linux rpm file
    setup.py bdist --format=wininst
    setup.py bdist --format=rpm
    
    python setup.py build
    python setup.py install
    

Remarks:
1、Local Network Test Proxy
    yum install squid -y
    systemctl start squid
then the squid is listened on the default 3128 proxy port
    

'''