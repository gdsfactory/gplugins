uv:
	curl -LsSf https://astral.sh/uv/0.5.5/install.sh | sh

venv:
	uv venv --python 3.11

install:
	uv venv --python 3.11
	uv pip install -e .[dev,docs,devsim,femwell,gmsh,klayout,meow,meshwell,ray,sax,schematic,tidy3d,vlsir]
	uv run pre-commit install

dev: test-data gmsh elmer install

gmsh:
	sudo apt-get update
	sudo apt-get install -y python3-gmsh gmsh libglu1-mesa libxi-dev libxmu-dev libglu1-mesa-dev

elmer:
	sudo apt-add-repository ppa:elmer-csc-ubuntu/elmer-csc-ppa
	sudo apt-get update
	sudo apt-get install -y elmerfem-csc mpich

meep:
	conda install -c conda-forge pymeep=*=mpi_mpich_* nlopt -y\

test:
	pytest

cov:
	pytest --cov=gplugins

test-data:
	git clone https://github.com/gdsfactory/gdsfactory-test-data.git -b test-data test-data

test-data-ssh:
	git clone git@github.com:gdsfactory/gdsfactory-test-data.git -b test-data test-data

git-rm-merged:
	git branch -D `git branch --merged | grep -v \* | xargs`

update-pre:
	pre-commit autoupdate

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
	uv run jb build docs

.PHONY: drc doc docs
