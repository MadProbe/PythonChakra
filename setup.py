"""
Parts of this file were taken from the discord.py project
(https://github.com/Rapptz/discord.py) which have been permitted for use under the
MIT license.
"""

from setuptools import setup
import re

requirements = []
with open('requirements.txt') as f:
    requirements = f.read().splitlines()

version = ''
with open('python_chakra/__init__.py') as f:
    version = re.search(r'^__version__\s*=\s*[\'"]([^\'"]*)[\'"]',
                        f.read(), re.MULTILINE).group(1)

if not version:
    raise RuntimeError('version is not set')

readme = ''
with open('readme.md') as f:
    readme = f.read()

setup(name='python-chakra',
      author='MadProbe',
      url='https://github.com/MadProbe/PythonChakra',
      project_urls={"Issue tracker": "https://github.com/MadProbe/PythonChakra/issues"},
      version=version,
      packages=['python_chakra', 'python_chakra.utils'],
      license='MIT',
      long_description=readme,
      long_description_content_type="text/x-markdown",
      description='Python wrapper for ChakraCore',
      include_package_data=True,
      install_requires=requirements,
      python_requires='>=3.9.0')
