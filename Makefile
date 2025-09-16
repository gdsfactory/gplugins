uv:
	curl -LsSf https://astral.sh/uv/install.sh | sh

venv:
	uv venv --python 3.11

install:
	uv venv --python 3.11
	uv pip install -e .[dev,docs,femwell,gmsh,meow,sax,tidy3d,klayout,vlsir]
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

uv-test:
	@for plugin in femwell gmsh meow sax tidy3d klayout vlsir path_length_analysis; do \
		uv run pytest gplugins/$$plugin; \
	done

cov:
	uv run pytest gplugins/femwell gplugins/meshwell gplugins/meow gplugins/sax gplugins/tidy3d gplugins/klayout gplugins/vlsir gplugins/path_length_analysis --cov=gplugins/femwell --cov=gplugins/meshwell --cov=gplugins/meow --cov=gplugins/sax --cov=gplugins/tidy3d --cov=gplugins/klayout --cov=gplugins/vlsir --cov=gplugins/path_length_analysis

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
	PYVISTA_OFF_SCREEN=0 PYVISTA_JUPYTER_BACKEND=html uv run jb build docs

clean:
	rm -rf dist
	rm -rf build
	rm -rf .eggs
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf .venv

.PHONY: drc doc docs dev
