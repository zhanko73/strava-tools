import os

from setuptools import setup, find_packages

VERSION = '0.0.1'
DESCRIPTION = 'Strava Command-Line Tools'

here = os.path.abspath(os.path.dirname(__file__))
with open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

print(find_packages())

setup(
    python_requires='>=3.5',
    name='strava-tools',
    description=DESCRIPTION,
    long_description=long_description,
    long_description_content_type='text/markdown',
    version=VERSION,
    author='Pierrick Terrettaz',
    author_email='pierrick@gmail.com',
    url='https://github.com/terrettaz/strava-tools',
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Natural Language :: English",
        "Topic :: Utilities"
    ],
    install_requires=[
        'beautifulsoup4',
        'bs4',
        'lxml',
        'requests',
        'texttables'
    ],
     entry_points={
        'console_scripts': [
            'stravatools = stravatools.cli:main',
        ],
    },
)