import multiprocessing
from setuptools import setup, find_packages
setup(
    name = "online_learning_computations",
    version = "0.30",
    packages = find_packages(),

    # Dependencies on other packages:
    # Couldn't get numpy install to work without
    # an out-of-band: sudo apt-get install python-dev
    setup_requires   = ['nose>=1.1.2'],
    install_requires = ['pymysql_utils>=0.33', 
			'configparser>=3.3.0r2', 
			'argparse>=1.2.1', 
			'numpy>=1.8.0'
			],
    tests_require    = ['sentinels>=0.0.6', 'nose>=1.0'],

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
