
install: 
	pip install -e .[dev]
	pre-commit install

dev:
	pip install -e .[dev,docs,database,devsim,femwell,gmsh,kfactory,meow,meshwell,ray,sax,tidy3d]
	conda install -c conda-forge pymeep=*=mpi_mpich_* nlopt -y

test:
	pytest -s --ignore=gplugins/gtidy3d/write_sparameters.py --ignore=gplugins/gtidy3d/write_sparameters_grating_coupler.py

cov:
	pytest --cov=gplugins

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

