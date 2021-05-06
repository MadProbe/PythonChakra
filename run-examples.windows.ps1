pip install . --use-feature=in-tree-build > $null
rm.exe -rf .\python_chakra.egg-info .\build
python.exe .\examples\main.py
