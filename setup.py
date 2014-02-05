import multiprocessing
from setuptools import setup, find_packages
setup(
    name = "online_learning_computations",
    version = "0.1",
    packages = find_packages(),

    # Dependencies on other packages:
    # Couldn't get numpy install to work without
    # an out-of-band: sudo apt-get install python-dev
    setup_requires   = ['nose>=1.1.2'],
    install_requires = ['ijson>=1.0', 
			'pymongo>=2.6.2', 
			'pymysql3>=0.5', 
			'configparser>=3.3.0r2', 
			'argparse>=1.2.1', 
			'unidecode>=0.04.14', 
			'numpy>=1.8.0'
			],
    # tests_require    = ['mongomock>=1.0.1', 'sentinels>=0.0.6', 'nose>=1.0'],

    # Unit tests; they are initiated via 'python setup.py test'
    #test_suite       = 'json_to_relation/test',
    test_suite       = 'nose.collector', 

    package_data = {
        # If any package contains *.txt or *.rst files, include them:
     #   '': ['*.txt', '*.rst'],
        # And include any *.msg files found in the 'hello' package, too:
     #   'hello': ['*.msg'],
    },

    # metadata for upload to PyPI
    author = "Andreas Paepcke",
    #author_email = "me@example.com",
    description = "Computes statistics from OpenEdX platform data.",
    license = "BSD",
    keywords = "OpenEdX, learning science",
    url = "https://github.com/paepcke/online_learning_computations",   # project home page, if any
)