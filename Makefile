
install:
	pip install -e .[dev,docs,devsim,femwell,gmsh,meow,meshwell,ray,sax,schematic,tidy3d,web,vlsir]
	pre-commit install

dev: test-data gmsh elmer install meep

gmsh:
	sudo apt-get install -y python3-gmsh gmsh libglu1-mesa libxi-dev libxmu-dev libglu1-mesa-dev

meep:
	micromamba install -c conda-forge pymeep=*=mpi_mpich_* nlopt -y

elmer:
	sudo apt-add-repository ppa:elmer-csc-ubuntu/elmer-csc-ppa
	sudo apt-get update
	sudo apt-get install -y elmerfem-csc mpich

test:
	pytest

cov:
	pytest --cov=gplugins

test-data:
	git clone https://github.com/gdsfactory/gdsfactory-test-data.git -b test-data test-data

test-data-developers:
	git clone git@github.com:gdsfactory/gdsfactory-test-data.git -b test-data test-data

git-rm-merged:
	git branch -D `git branch --merged | grep -v \* | xargs`

update-pre:
	pre-commit autoupdate

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

notebooks-clean:
	jupytext docs/notebooks/*.py --to py  --update-metadata '{"kernelspec": {"display_name": "", "language": "", "name": ""}}'

docs:
	jb build docs

.PHONY: drc doc docs
