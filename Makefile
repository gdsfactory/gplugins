
install:
	pip install -e .[dev]
	pre-commit install

dev: test-data
	pip install -e .[dev,docs,database,devsim,femwell,gmsh,kfactory,meow,meshwell,ray,sax,tidy3d]
	conda install -c conda-forge pymeep=*=mpi_mpich_* nlopt -y
	sudo apt-get install -y python3-gmsh gmsh
	sudo apt install libglu1-mesa libxi-dev libxmu-dev libglu1-mesa-dev

test:
	pytest \
		--ignore=gplugins/gtidy3d/tests/test_write_sparameters_grating_coupler.py \
   		--ignore=gplugins/gtidy3d/tests/test_write_sparameters_grating_coupler.py

cov:
	pytest --cov=gplugins \
		--ignore=gplugins/gtidy3d/tests/test_write_sparameters_grating_coupler.py \
   		--ignore=gplugins/gtidy3d/tests/test_write_sparameters_grating_coupler.py

test-data:
	git clone https://github.com/gdsfactory/gdsfactory-test-data.git -b test-data test-data

mypy:
	mypy . --ignore-missing-imports

pylint:
	pylint gplugins

ruff:
	ruff --fix gplugins/*.py

git-rm-merged:
	git branch -D `git branch --merged | grep -v \* | xargs`

update:
	pur

update-pre:
	pre-commit autoupdate --bleeding-edge

git-rm-merged:
	git branch -D `git branch --merged | grep -v \* | xargs`

release:
	git push
	git push origin --tags

build:
	rm -rf dist
	pip install build
	python -m build

jupytext:
	jupytext docs/**/*.ipynb --to py

notebooks:
	jupytext docs/**/*.py --to ipynb


docs:
	jb build docs

.PHONY: drc doc docs
